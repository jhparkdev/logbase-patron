"""AI 호출 이력(ai_requests)과 원문(ai_request_payloads)에 쓰는 유일한 곳.

ai_requests 는 모든 사용량·비용 집계의 원천이라 쓰는 문을 이 파일 하나로 둔다.
상태를 바꾸는 함수는 모두 조건부 갱신이다. 현재 상태가 허용한 값일 때만 바꾸고,
실제로 바꿨는지를 돌려준다. 취소와 정상 완료가 같은 칸에 거의 동시에 와도 DB 가 먼저 도착한
쪽만 인정하므로, 끝난 호출의 상태·비용은 다시 쓰이지 않는다.

넘겨받은 세션 안에서만 일하고 commit 하지 않는다. 트랜잭션은 부르는 쪽이 정한다.
함수 이름에 simulation 을 붙인 것은 시뮬레이터 호출용이라는 뜻이다. 연결 테스트나 외부 호출 기록
같은 다른 기능은 같은 파일에 자기 이름의 함수를 더한다.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    AIRequestPayload,
    CostStatus,
    ErrorType,
    RequestStatus,
)
from app.openrouter.errors import USER_MESSAGES
from app.openrouter.errors import ErrorType as CallErrorType
from app.services.simulation_ports import NewRequest, SlotRecord

_OPEN = (RequestStatus.PENDING, RequestStatus.RUNNING)
_UNFINISHED_ERROR_MESSAGE = USER_MESSAGES[CallErrorType.UNKNOWN_ERROR]


async def create_simulation_request(session: AsyncSession, request: NewRequest) -> None:
    """시뮬레이터 호출 이력을 PENDING 으로 만든다. 모델을 부르기 전에 Request ID 를 먼저 남긴다.

    비용은 아직 모르므로 UNKNOWN 이고 금액은 비워 둔다(0 이 아니다).
    """
    session.add(
        AIRequest(
            request_id=request.request_id,
            usage_origin=request.usage_origin,
            key_id=request.key_id,
            project_id=request.project_id,
            executed_by=request.executed_by,
            service_id=request.service_id,
            simulation_id=request.simulation_id,
            call_purpose=request.call_purpose,
            attempt_no=request.attempt_no,
            model_id=request.model_id,
            requested_model=request.requested_model,
            requested_provider=request.requested_provider,
            routing_policy=request.routing_policy,
            execution_config=request.execution_config,
            input_hash=request.input_hash,
            status=RequestStatus.PENDING,
            requested_at=request.requested_at,
            cost_status=CostStatus.UNKNOWN,
            data_source=request.data_source,
        )
    )
    # 칸 결과(simulation_results)가 이 행을 외래키로 가리키므로 바로 보낸다
    await session.flush()


async def start_simulation_request(
    session: AsyncSession, request_id: uuid.UUID
) -> bool:
    """PENDING 일 때만 RUNNING 으로 바꾼다. 이미 취소되었으면 False 라서 호출하지 않는다.

    호출 이력에는 시작 시각 칸이 없어서 시각을 받지 않는다.
    """
    return await _transition(
        session, request_id, (RequestStatus.PENDING,), status=RequestStatus.RUNNING
    )


async def finish_simulation_request(
    session: AsyncSession, request_id: uuid.UUID, record: SlotRecord, now: datetime
) -> bool:
    """RUNNING 일 때만 호출 결과를 기록한다. 이미 취소나 종료로 끝났으면 False 이고 아무것도 쓰지 않는다."""
    confirmed = record.cost_status == CostStatus.CONFIRMED
    return await _transition(
        session,
        request_id,
        (RequestStatus.RUNNING,),
        status=record.status,
        error_type=record.error_type,
        error_message=record.error_message,
        http_status=record.http_status,
        finish_reason=record.finish_reason,
        completed_at=now,
        latency_ms=record.latency_ms,
        external_generation_id=record.external_generation_id,
        actual_provider=record.actual_provider,
        actual_model=record.actual_model,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cached_tokens=record.cached_tokens,
        cache_write_tokens=record.cache_write_tokens,
        reasoning_tokens=record.reasoning_tokens,
        cost_usd=record.cost_usd,
        cost_status=record.cost_status,
        cost_source=record.cost_source,
        cost_confirmed_at=now if confirmed else None,
    )


async def cancel_simulation_request(
    session: AsyncSession, request_id: uuid.UUID, now: datetime
) -> bool:
    """PENDING 이나 RUNNING 일 때만 CANCELLED 로 바꾼다. 이미 끝났으면 False.

    취소해도 업체 쪽 처리 비용이 나갈 수 있으므로 비용은 건드리지 않는다(미확인 그대로).
    """
    return await _transition(
        session,
        request_id,
        _OPEN,
        status=RequestStatus.CANCELLED,
        completed_at=now,
    )


async def fail_unfinished_simulation_request(
    session: AsyncSession, request_id: uuid.UUID, now: datetime
) -> bool:
    """서버가 멈춰 끝나지 못한 호출을 실패로 닫는다. 복구 작업이 부른다.

    호출 중이던 요청은 이미 과금됐을 수 있어서 비용은 미확인으로 둔다(0 으로 닫지 않는다).
    """
    return await _transition(
        session,
        request_id,
        _OPEN,
        status=RequestStatus.FAILED,
        error_type=ErrorType.UNKNOWN_ERROR,
        error_message=_UNFINISHED_ERROR_MESSAGE,
        completed_at=now,
    )


async def save_simulation_payload(
    session: AsyncSession,
    request_id: uuid.UUID,
    messages: Sequence[dict[str, str]],
    response_text: str | None,
) -> None:
    """보낸 프롬프트와 받은 응답 원문을 저장한다. 이미 저장된 원문은 덮어쓰지 않는다."""
    await session.execute(
        insert(AIRequestPayload)
        .values(
            request_id=request_id,
            request_messages=list(messages),
            response_text=response_text,
        )
        .on_conflict_do_nothing(index_elements=[AIRequestPayload.request_id])
    )


async def _transition(
    session: AsyncSession,
    request_id: uuid.UUID,
    allowed: Sequence[RequestStatus],
    **values: Any,
) -> bool:
    """현재 상태가 allowed 안에 있을 때만 values 로 바꾸고, 바꿨는지를 돌려준다.

    조건을 UPDATE 문 안에 넣어 읽기와 쓰기 사이에 다른 쪽이 끼어들 틈을 없앤다.
    """
    result = await session.execute(
        update(AIRequest)
        .where(AIRequest.request_id == request_id, AIRequest.status.in_(allowed))
        .values(**values)
        .returning(AIRequest.request_id)
        .execution_options(synchronize_session=False)
    )
    return result.scalar_one_or_none() is not None

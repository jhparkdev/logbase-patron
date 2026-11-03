"""services/requests.py 가 채우지 못하는 시뮬레이터 호출 이력 쓰기.

생성·시작·종료·취소·원문 저장은 requests.py 가 맡는다. 여기에는 그 함수가 받지 않는 값과
서버 재시작 복구만 둔다. ai_requests 에 쓰는 문이 늘지 않도록 requests.py 로 옮길 수 있는 것은 옮긴다.

상태를 바꾸는 함수는 조건부 갱신이고, 실제로 바꿨는지를 돌려준다. 넘겨받은 세션 안에서만 일하고
commit 하지 않는다. 트랜잭션은 부르는 쪽이 정한다.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, ErrorType, RequestStatus
from app.openrouter.errors import USER_MESSAGES
from app.openrouter.errors import ErrorType as CallErrorType
from app.services.simulation_ports import SlotRecord

_OPEN = (RequestStatus.PENDING, RequestStatus.RUNNING)
_UNFINISHED_ERROR_MESSAGE = USER_MESSAGES[CallErrorType.UNKNOWN_ERROR]


async def save_finish_details(
    session: AsyncSession, request_id: uuid.UUID, record: SlotRecord
) -> bool:
    """requests.record_finished 가 받지 않는 종료 부가 정보를 같은 호출 이력에 더한다.

    record_finished 가 True 였던 같은 트랜잭션에서만 부른다. 그 UPDATE 가 행을 잠그고 있어 둘 사이에
    다른 처리가 끼어들 수 없다. 기록한 종료 상태와 같을 때만 쓰므로 취소된 행에는 쓰지 않는다.
    """
    return await _transition(
        session,
        request_id,
        (record.status,),
        error_message=record.error_message,
        http_status=record.http_status,
        finish_reason=record.finish_reason,
        cached_tokens=record.cached_tokens,
        cache_write_tokens=record.cache_write_tokens,
        reasoning_tokens=record.reasoning_tokens,
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


async def keep_late_generation_id(
    session: AsyncSession, request_id: uuid.UUID, generation_id: str | None
) -> bool:
    """취소로 먼저 끝난 호출에 늦게 도착한 응답의 호출 ID 를 비용 대조용으로 남긴다(J-03).

    상태와 비용은 바꾸지 않는다. 비용은 이 ID 로 OpenRouter 를 조회하는 대조 작업만 갱신한다.
    이미 아는 ID 는 덮어쓰지 않는다. 취소된 호출이 아니면 아무것도 쓰지 않고 False 를 돌려준다.
    """
    result = await session.execute(
        update(AIRequest)
        .where(
            AIRequest.request_id == request_id,
            AIRequest.status == RequestStatus.CANCELLED,
        )
        .values(
            external_generation_id=func.coalesce(
                AIRequest.external_generation_id, generation_id
            )
        )
        .returning(AIRequest.request_id)
        .execution_options(synchronize_session=False)
    )
    return result.scalar_one_or_none() is not None


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

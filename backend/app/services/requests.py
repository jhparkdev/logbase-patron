"""호출 이력 생성·원문 저장과 조건부 시작·종료·취소를 담당한다.

각 함수는 commit하지 않는다. 호출자가 트랜잭션을 확정해야 변경이 최종 반영된다.
병렬 작업마다 별도의 AsyncSession을 사용하고, 한 세션을 동시에 공유하지 않는다.
False는 대상이 없거나 현재 상태가 조건에 맞지 않다는 뜻이며 DB 오류는 예외로 전달한다.
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from pydantic import JsonValue
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    AIRequestPayload,
    APIKey,
    CostSource,
    CostStatus,
    RequestStatus,
)
from app.services.request_records import PendingRequest, RequestResult

_FINISHED_STATUSES = (
    RequestStatus.SUCCESS,
    RequestStatus.FAILED,
    RequestStatus.TIMEOUT,
)
_CANCELLABLE_STATUSES = (RequestStatus.PENDING, RequestStatus.RUNNING)


class KeyServiceMismatchError(Exception):
    """Key에 정해진 서비스와 다른 서비스의 호출을 기록하려 할 때 발생한다."""


async def create_pending(session: AsyncSession, request: PendingRequest) -> None:
    """시뮬레이터가 만든 ID와 실행 조건으로 PENDING 이력을 생성한다.

    금액은 미확인(NULL)으로 시작한다. 중복 ID나 잘못된 참조는 DB 오류로 전달하며,
    기존 이력을 초기화하거나 덮어쓰지 않는다. 시뮬레이션 전체의 commit은 호출자가 한다.
    외부 모델 호출은 이 이력과 시뮬레이션 접수 정보가 commit된 뒤에 시작해야 한다.
    Key에 서비스가 정해져 있으면 그 서비스의 호출만 받는다. NULL은 여러 서비스가 함께 쓰는 Key다.
    """
    key_service_id = await session.scalar(
        select(APIKey.service_id).where(APIKey.key_id == request.key_id)
    )
    if key_service_id is not None and key_service_id != request.service_id:
        raise KeyServiceMismatchError("Key에 정해진 서비스와 호출의 서비스가 다릅니다.")
    await session.execute(
        insert(AIRequest).values(
            request_id=request.request_id,
            simulation_id=request.simulation_id,
            usage_origin=request.usage_origin,
            call_purpose=request.call_purpose,
            attempt_no=request.attempt_no,
            project_id=request.project_id,
            key_id=request.key_id,
            service_id=request.service_id,
            executed_by=request.executed_by,
            model_id=request.model_id,
            requested_model=request.requested_model,
            requested_provider=request.requested_provider,
            routing_policy=dict(request.routing_policy),
            execution_config=dict(request.execution_config),
            input_hash=request.input_hash,
            requested_at=_as_utc(request.requested_at),
            data_source=request.data_source,
            status=RequestStatus.PENDING,
            cost_status=CostStatus.UNKNOWN,
            cost_usd=None,
            cost_source=None,
        )
    )


async def mark_running(
    session: AsyncSession, request_id: uuid.UUID, now: datetime
) -> bool:
    """PENDING일 때만 RUNNING으로 바꾼다. 이미 시작했거나 종료된 호출은 바꾸지 않는다."""
    # 시작 시각 전용 컬럼이 없으므로 requested_at은 유지한다. now는 시간대만 검증한다.
    _as_utc(now)
    return await _change(
        session, request_id, (RequestStatus.PENDING,), status=RequestStatus.RUNNING
    )


async def record_finished(
    session: AsyncSession,
    request_id: uuid.UUID,
    record: RequestResult,
    now: datetime,
    *,
    cost_source: CostSource | None = None,
    price_id: int | None = None,
) -> bool:
    """RUNNING일 때만 종료 결과를 함께 저장한다. 취소는 cancel_request로 기록한다.

    비용 금액·상태·근거는 호출자가 판단한 값을 받으며 이 함수가 추정하거나 분류하지 않는다.
    False인 늦은 완료 결과의 비용 대조는 호출자가 별도 경로로 처리해야 한다.
    """
    if record.status not in _FINISHED_STATUSES:
        raise ValueError("종료 기록은 SUCCESS, FAILED, TIMEOUT만 허용합니다.")
    completed_at = _as_utc(now)
    # 상태와 결과를 함께 갱신해야, 취소가 먼저 확정됐을 때 비용·토큰만 뒤늦게 섞이지 않는다.
    return await _change(
        session,
        request_id,
        (RequestStatus.RUNNING,),
        status=record.status,
        error_type=record.error_type,
        completed_at=completed_at,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cost_usd=record.cost_usd,
        cost_status=record.cost_status,
        cost_source=cost_source,
        price_id=price_id,
        cost_confirmed_at=(
            completed_at if record.cost_status == CostStatus.CONFIRMED else None
        ),
        actual_provider=record.actual_provider,
        actual_model=record.actual_model,
        latency_ms=record.latency_ms,
        external_generation_id=record.external_generation_id,
    )


async def cancel_request(
    session: AsyncSession, request_id: uuid.UUID, now: datetime
) -> bool:
    """PENDING·RUNNING만 취소한다. 청구 여부는 미확인으로 두고 종료 시각을 기록한다."""
    # 로컬 취소가 외부 업체의 청구 취소를 보장하지는 않는다. 금액을 0으로 확정하지 않는다.
    # 외부 호출 ID는 지우지 않아 나중에 청구 여부를 조회할 수 있게 한다.
    return await _change(
        session,
        request_id,
        _CANCELLABLE_STATUSES,
        status=RequestStatus.CANCELLED,
        error_type=None,
        completed_at=_as_utc(now),
        cost_status=CostStatus.UNKNOWN,
        cost_usd=None,
        cost_source=None,
        cost_confirmed_at=None,
        price_id=None,
    )


async def _change(
    session: AsyncSession,
    request_id: uuid.UUID,
    allowed: tuple[RequestStatus, ...],
    **values: object,
) -> bool:
    # 상태 확인을 따로 SELECT하면 그 사이 다른 처리가 종료시킬 수 있어 한 UPDATE로 묶는다.
    result = await session.execute(
        update(AIRequest)
        .where(AIRequest.request_id == request_id, AIRequest.status.in_(allowed))
        .values(**values)
        .returning(AIRequest.request_id)
    )
    # RETURNING은 실제로 갱신한 행만 돌려준다. 조건에 맞는 행이 없으면 None이다.
    return result.scalar_one_or_none() is not None


async def save_payload(
    session: AsyncSession,
    request_id: uuid.UUID,
    messages: Sequence[Mapping[str, JsonValue]],
    response_text: str | None,
) -> None:
    """요청·응답 원문을 한 번 저장하고, 중복이면 기존 원문을 보존하며 DB 오류를 전달한다.

    종료 결과와 함께 확정하려면 상태 변경이 True인 경우에만 같은 트랜잭션에서 호출한다.
    응답 없이 먼저 저장한 행을 나중에 갱신하는 함수는 아니므로 저장 시점을 호출자가 정한다.
    """
    await session.execute(
        insert(AIRequestPayload).values(
            request_id=request_id,
            # 설계 SQL·seed와 동일하게 messages를 JSONB 배열 그대로 저장한다.
            request_messages=[dict(message) for message in messages],
            response_text=response_text,
        )
    )


def _as_utc(now: datetime) -> datetime:
    if now.utcoffset() is None:
        raise ValueError("now에는 시간대 정보가 필요합니다.")
    return now.astimezone(UTC)

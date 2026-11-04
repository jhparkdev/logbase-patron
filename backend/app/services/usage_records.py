"""고객 서비스가 보낸 호출 기록을 Key·고객·작업에 연결해 저장한다.

귀속은 Key 단위다. 기록에 적힌 고객 코드는 Key에 연결된 고객과 같은지 확인하는 용도로만 쓰고,
다르면 임의로 귀속하지 않고 거절한다. 프로젝트 Key로 들어온 고객 호출은 고객을 알 수 없으므로
customer_id 없이 저장해 미분류로 집계된다. 같은 요청 ID를 다시 보내면 처음 값을 바꾸지 않는다.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    APIKey,
    Customer,
    DataSource,
    KeyOwnerType,
    ModelRegistry,
    RequestStatus,
    Task,
    UsageOrigin,
)
from app.schemas.usage_record import UsageRecordCreate, UsageRecordReceipt
from app.services import requests
from app.services.request_records import FinishedCall

MILLISECONDS_PER_SECOND = 1000


class UsageRecordKeyNotFoundError(LookupError):
    """기록에 적힌 key_id 가 등록된 Key가 아니다."""


class UsageRecordKeyUnusableError(Exception):
    """Key에 서비스가 연결돼 있지 않아 어느 서비스의 호출인지 알 수 없다."""


class UsageRecordCustomerMismatchError(Exception):
    """기록의 고객 코드가 Key에 연결된 고객과 다르거나 등록되지 않은 고객이다."""


class UsageRecordConflictError(Exception):
    """OpenRouter 응답 id 가 다른 요청 ID의 기록에 이미 쓰였다."""


def _latency_ms(record: UsageRecordCreate) -> int | None:
    if record.latency_ms is not None:
        return record.latency_ms
    if record.completed_at is None:
        return None
    elapsed = record.completed_at - record.requested_at
    return round(elapsed.total_seconds() * MILLISECONDS_PER_SECOND)


async def _customer_of(
    session: AsyncSession, key: APIKey, customer_code: str
) -> int | None:
    """기록의 고객 코드가 Key의 고객과 같을 때만 그 고객을 돌려준다. 프로젝트 Key는 고객이 없다(None)."""
    if key.owner_type != KeyOwnerType.CUSTOMER:
        return None
    declared = await session.scalar(
        select(Customer.customer_id).where(Customer.customer_code == customer_code)
    )
    if declared is None or declared != key.customer_id:
        raise UsageRecordCustomerMismatchError
    return declared


async def _task_for(
    session: AsyncSession,
    record: UsageRecordCreate,
    *,
    service_id: int,
    customer_id: int | None,
) -> Task:
    """서비스 안에서 작업 ID가 같은 호출을 한 작업으로 묶는다. 없으면 만들고, 시작·끝은 묶인 호출 전체를 덮는다."""
    await session.execute(
        pg_insert(Task)
        .values(
            task_id=uuid.uuid7(),
            external_task_ref=record.task_ref,
            usage_origin=UsageOrigin.CUSTOMER_SERVICE,
            customer_id=customer_id,
            project_id=None,
            service_id=service_id,
            task_type=record.task_type,
            data_source=DataSource.LIVE,
        )
        .on_conflict_do_nothing(
            index_elements=[Task.service_id, Task.external_task_ref]
        )
    )
    task = await session.scalar(
        select(Task).where(
            Task.service_id == service_id,
            Task.external_task_ref == record.task_ref,
        )
    )
    assert task is not None
    task.started_at = _earlier(task.started_at, record.requested_at)
    if record.completed_at is not None:
        task.completed_at = _later(task.completed_at, record.completed_at)
    return task


def _earlier(current: datetime | None, other: datetime) -> datetime:
    return other if current is None or other < current else current


def _later(current: datetime | None, other: datetime) -> datetime:
    return other if current is None or other > current else current


async def _already_stored(session: AsyncSession, request_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(AIRequest.request_id).where(AIRequest.request_id == request_id)
    )
    return found is not None


async def save_usage_record(
    session: AsyncSession, record: UsageRecordCreate
) -> UsageRecordReceipt:
    """기록 한 건을 저장하고 commit한다. 거절하면 아무것도 저장하지 않는다."""
    key = await session.scalar(select(APIKey).where(APIKey.key_id == record.key_id))
    if key is None:
        raise UsageRecordKeyNotFoundError
    if key.service_id is None:
        raise UsageRecordKeyUnusableError
    customer_id = await _customer_of(session, key, record.customer_code)

    # 다시 보낸 요청은 작업이나 호출을 건드리지 않고 이미 저장되었다고만 알린다
    if await _already_stored(session, record.request_id):
        return UsageRecordReceipt(request_id=record.request_id, stored=False)
    generation_id = record.openrouter_generation_id
    if generation_id is not None:
        used = await session.scalar(
            select(AIRequest.request_id).where(
                AIRequest.external_generation_id == generation_id
            )
        )
        if used is not None:
            raise UsageRecordConflictError

    task = await _task_for(
        session, record, service_id=key.service_id, customer_id=customer_id
    )
    model_id = await session.scalar(
        select(ModelRegistry.model_id).where(
            ModelRegistry.openrouter_model_id == record.model
        )
    )
    inserted = await requests.record_finished_call(
        session,
        FinishedCall(
            request_id=record.request_id,
            key_id=key.key_id,
            customer_id=customer_id,
            service_id=key.service_id,
            task_id=task.task_id,
            model_id=model_id,
            requested_model=record.model,
            actual_model=record.actual_model,
            actual_provider=record.actual_provider,
            finish_reason=record.finish_reason,
            status=RequestStatus(record.status.value),
            error_type=record.error_type,
            http_status=record.http_status,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            cached_tokens=record.cached_tokens,
            reasoning_tokens=record.reasoning_tokens,
            cost_usd=record.cost_usd,
            latency_ms=_latency_ms(record),
            requested_at=record.requested_at,
            completed_at=record.completed_at,
            external_generation_id=generation_id,
        ),
    )
    if not inserted:
        # 동시에 같은 요청이 먼저 저장된 경우가 아니면 응답 id 충돌이다
        if await _already_stored(session, record.request_id):
            return UsageRecordReceipt(request_id=record.request_id, stored=False)
        raise UsageRecordConflictError
    await session.commit()
    return UsageRecordReceipt(request_id=record.request_id, stored=True)

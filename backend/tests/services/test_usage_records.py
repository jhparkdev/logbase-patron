"""services/usage_records.py 테스트. 고객 서비스가 보낸 호출 기록을 Key·고객·작업에 연결해 저장하는 규칙을 본다."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, Task
from app.schemas.usage_record import UsageRecordCreate
from app.services.usage_records import (
    UsageRecordConflictError,
    UsageRecordCustomerMismatchError,
    UsageRecordKeyNotFoundError,
    UsageRecordKeyUnusableError,
    save_usage_record,
)
from tests.db_helpers import Factory


def record(**overrides: Any) -> UsageRecordCreate:
    body: dict[str, Any] = {
        "request_id": str(uuid.uuid4()),
        "key_id": 1,
        "customer_code": "CUST-X",
        "task_ref": "detail-page-1001",
        "task_type": "상세페이지 생성",
        "model": "openai/gpt-4o-mini",
        "requested_at": "2026-10-10T01:00:00Z",
        "completed_at": "2026-10-10T01:00:02Z",
        "status": "SUCCESS",
    }
    body.update(overrides)
    return UsageRecordCreate.model_validate(body)


async def customer_key(factory: Factory) -> dict[str, Any]:
    customer = await factory.customer()
    service = await factory.service(service_type="CUSTOMER_FACING")
    key = await factory.api_key(
        owner_type="CUSTOMER",
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
    )
    return {
        "customer": customer,
        "service": service,
        "key": key,
        "ids": {"key_id": key["key_id"], "customer_code": customer["customer_code"]},
    }


async def stored(session: AsyncSession) -> list[AIRequest]:
    return list(await session.scalars(select(AIRequest)))


async def count(session: AsyncSession, table: type[Task | AIRequest]) -> int:
    return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_a_success_record_is_saved_for_the_keys_customer_and_service(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)
    request = record(
        **owner["ids"],
        input_tokens=120,
        output_tokens=30,
        cached_tokens=20,
        reasoning_tokens=5,
        cost_usd="0.000045",
        openrouter_generation_id="gen-abc",
        actual_model="openai/gpt-4o-mini-2024",
        actual_provider="OpenAI",
        finish_reason="stop",
    )

    receipt = await save_usage_record(db_session, request)

    assert receipt.stored is True
    assert receipt.request_id == request.request_id
    [row] = await stored(db_session)
    assert row.request_id == request.request_id
    assert row.usage_origin == "CUSTOMER_SERVICE"
    assert row.customer_id == owner["customer"]["customer_id"]
    assert row.service_id == owner["service"]["service_id"]
    assert row.key_id == owner["key"]["key_id"]
    assert (row.project_id, row.executed_by) == (None, None)
    assert row.data_source == "LIVE"
    assert row.status == "SUCCESS"
    assert (row.input_tokens, row.output_tokens) == (120, 30)
    assert (row.cached_tokens, row.reasoning_tokens) == (20, 5)
    assert row.external_generation_id == "gen-abc"
    assert (row.actual_model, row.actual_provider) == (
        "openai/gpt-4o-mini-2024",
        "OpenAI",
    )
    assert row.cost_usd == Decimal("0.000045")
    assert row.cost_status == "CONFIRMED"
    assert row.cost_source == "API_RESPONSE"
    assert row.latency_ms == 2000


async def test_a_given_latency_wins_over_the_time_difference(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    await save_usage_record(db_session, record(**owner["ids"], latency_ms=1480))

    [row] = await stored(db_session)
    assert row.latency_ms == 1480


async def test_a_missing_cost_is_unknown_not_zero(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    await save_usage_record(db_session, record(**owner["ids"]))

    [row] = await stored(db_session)
    assert row.cost_usd is None
    assert row.cost_status == "UNKNOWN"
    assert row.cost_source is None


async def test_a_failed_call_keeps_its_error_and_its_cost_stays_unknown(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    await save_usage_record(
        db_session,
        record(
            **owner["ids"],
            status="FAILED",
            error_type="PROVIDER_ERROR",
            http_status=502,
            cost_usd="0.5",
        ),
    )

    [row] = await stored(db_session)
    assert (row.status, row.error_type, row.http_status) == (
        "FAILED",
        "PROVIDER_ERROR",
        502,
    )
    assert row.cost_usd is None
    assert row.cost_status == "UNKNOWN"


async def test_a_timeout_is_saved_without_a_completion_time(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    await save_usage_record(
        db_session, record(**owner["ids"], status="TIMEOUT", completed_at=None)
    )

    [row] = await stored(db_session)
    assert row.status == "TIMEOUT"
    assert row.error_type == "TIMEOUT_ERROR"
    assert row.completed_at is None
    assert row.latency_ms is None
    assert row.cost_status == "UNKNOWN"


async def test_sending_the_same_request_id_again_stores_it_only_once(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)
    request_id = str(uuid.uuid4())
    first = record(**owner["ids"], request_id=request_id, input_tokens=10)
    again = record(**owner["ids"], request_id=request_id, input_tokens=999)

    one = await save_usage_record(db_session, first)
    two = await save_usage_record(db_session, again)

    assert (one.stored, two.stored) == (True, False)
    [row] = await stored(db_session)
    # 처음 저장된 값을 바꾸지 않는다
    assert row.input_tokens == 10


async def test_calls_of_one_task_are_grouped_under_one_task(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    await save_usage_record(db_session, record(**owner["ids"]))
    await save_usage_record(
        db_session,
        record(
            **owner["ids"],
            requested_at="2026-10-10T01:00:05Z",
            completed_at="2026-10-10T01:00:09Z",
        ),
    )

    rows = await stored(db_session)
    assert len(rows) == 2
    assert rows[0].task_id is not None
    assert rows[0].task_id == rows[1].task_id
    [task] = list(await db_session.scalars(select(Task)))
    assert task.external_task_ref == "detail-page-1001"
    assert task.task_type == "상세페이지 생성"
    assert task.usage_origin == "CUSTOMER_SERVICE"
    assert task.customer_id == owner["customer"]["customer_id"]
    assert task.service_id == owner["service"]["service_id"]
    assert task.data_source == "LIVE"
    # 작업의 시작과 끝은 묶인 호출 전체를 덮는다
    assert task.started_at is not None
    assert task.started_at.isoformat().startswith("2026-10-10T01:00:00")
    assert task.completed_at is not None
    assert task.completed_at.isoformat().startswith("2026-10-10T01:00:09")


async def test_the_same_task_ref_in_another_service_is_another_task(
    db_session: AsyncSession, factory: Factory
) -> None:
    first = await customer_key(factory)
    second = await customer_key(factory)

    await save_usage_record(db_session, record(**first["ids"]))
    await save_usage_record(db_session, record(**second["ids"]))

    assert await count(db_session, Task) == 2


async def test_a_registered_model_is_linked_and_an_unknown_one_is_kept_by_name(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)
    model = await factory.model(openrouter_model_id="openai/gpt-4o-mini")

    await save_usage_record(db_session, record(**owner["ids"]))
    await save_usage_record(db_session, record(**owner["ids"], model="other/unknown"))

    by_name = {row.requested_model: row for row in await stored(db_session)}
    assert by_name["openai/gpt-4o-mini"].model_id == model["model_id"]
    assert by_name["other/unknown"].model_id is None


async def test_a_project_key_is_saved_as_unclassified(
    db_session: AsyncSession, factory: Factory
) -> None:
    service = await factory.service(service_type="CUSTOMER_FACING")
    key = await factory.api_key(owner_type="PROJECT", service_id=service["service_id"])

    receipt = await save_usage_record(
        db_session, record(key_id=key["key_id"], customer_code="CUST-ANY")
    )

    assert receipt.stored is True
    [row] = await stored(db_session)
    assert row.usage_origin == "CUSTOMER_SERVICE"
    assert row.customer_id is None
    assert row.key_id == key["key_id"]


async def test_an_unknown_key_is_rejected_and_nothing_is_saved(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    with pytest.raises(UsageRecordKeyNotFoundError):
        await save_usage_record(
            db_session,
            record(key_id=owner["key"]["key_id"] + 999, customer_code="CUST-X"),
        )

    assert await count(db_session, AIRequest) == 0
    assert await count(db_session, Task) == 0


async def test_a_customer_code_that_does_not_match_the_key_is_rejected(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)
    other = await factory.customer()

    with pytest.raises(UsageRecordCustomerMismatchError):
        await save_usage_record(
            db_session,
            record(key_id=owner["key"]["key_id"], customer_code=other["customer_code"]),
        )

    assert await count(db_session, AIRequest) == 0
    assert await count(db_session, Task) == 0


async def test_an_unregistered_customer_code_is_rejected(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)

    with pytest.raises(UsageRecordCustomerMismatchError):
        await save_usage_record(
            db_session,
            record(key_id=owner["key"]["key_id"], customer_code="NO-SUCH-CUSTOMER"),
        )


async def test_a_key_without_a_service_cannot_take_records(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    key = await factory.api_key(
        owner_type="CUSTOMER", customer_id=customer["customer_id"], service_id=None
    )

    with pytest.raises(UsageRecordKeyUnusableError):
        await save_usage_record(
            db_session,
            record(key_id=key["key_id"], customer_code=customer["customer_code"]),
        )


async def test_a_generation_id_already_used_by_another_request_is_a_conflict(
    db_session: AsyncSession, factory: Factory
) -> None:
    owner = await customer_key(factory)
    await save_usage_record(
        db_session, record(**owner["ids"], openrouter_generation_id="gen-1")
    )

    with pytest.raises(UsageRecordConflictError):
        await save_usage_record(
            db_session, record(**owner["ids"], openrouter_generation_id="gen-1")
        )

    assert await count(db_session, AIRequest) == 1

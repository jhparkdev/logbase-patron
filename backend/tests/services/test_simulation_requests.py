import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    CallPurpose,
    CostStatus,
    DataSource,
    ErrorType,
    RequestStatus,
    UsageOrigin,
)
from app.openrouter.result import CallStatus
from app.services.requests import (
    cancel_request,
    create_pending,
    mark_running,
    record_finished,
)
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_ports import NewRequest, SlotRecord
from app.services.simulation_requests import (
    fail_unfinished_simulation_request,
    save_finish_details,
)
from tests.db_helpers import T0, Factory
from tests.services.simulation_fakes import failed, ok

R = RequestStatus
START = T0 + timedelta(seconds=1)
END = T0 + timedelta(seconds=5)
MESSAGES = [{"role": "user", "content": "요약해 주세요"}]


async def new_request(factory: Factory, **overrides: Any) -> NewRequest:
    project = await factory.project()
    key = await factory.api_key(project_id=project["project_id"])
    service = await factory.service()
    user = await factory.user()
    run = await factory.simulation_run(
        project_id=project["project_id"],
        key_id=key["key_id"],
        executed_by=user["user_id"],
    )
    model = await factory.model()
    values: dict[str, Any] = {
        "request_id": uuid.uuid4(),
        "simulation_id": run["simulation_id"],
        "usage_origin": UsageOrigin.SIMULATION,
        "call_purpose": CallPurpose.EXPERIMENT,
        "attempt_no": 1,
        "project_id": project["project_id"],
        "key_id": key["key_id"],
        "service_id": service["service_id"],
        "executed_by": user["user_id"],
        "model_id": model["model_id"],
        "requested_model": model["openrouter_model_id"],
        "requested_provider": "DeepInfra",
        "routing_policy": {"allow_fallbacks": False, "order": ["DeepInfra"]},
        "execution_config": {"max_tokens": 4096},
        "input_hash": "a" * 64,
        "requested_at": T0,
        "data_source": DataSource.LIVE,
    }
    values.update(overrides)
    return NewRequest(**values)


async def saved(session: AsyncSession, request_id: uuid.UUID) -> AIRequest:
    row = await session.get(AIRequest, request_id)
    assert row is not None
    await session.refresh(row)
    return row


async def pending(factory: Factory, session: AsyncSession) -> uuid.UUID:
    request = await new_request(factory)
    await create_pending(session, request)
    return request.request_id


async def running(factory: Factory, session: AsyncSession) -> uuid.UUID:
    request_id = await pending(factory, session)
    assert await mark_running(session, request_id, START)
    return request_id


def success_record(**overrides: Any) -> SlotRecord:
    record = to_slot_record(ok('{"title": "a"}'), None)
    return record.__class__(**{**record.__dict__, **overrides})


# --- 종료 부가 정보 ---


async def finish_with_details(
    session: AsyncSession, request_id: uuid.UUID, record: SlotRecord
) -> bool:
    finished = await record_finished(
        session, request_id, record, END, cost_source=record.cost_source
    )
    return finished and await save_finish_details(session, request_id, record)


async def test_finish_details_fill_what_the_base_record_does_not_carry(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    record = success_record(cached_tokens=4, reasoning_tokens=1, finish_reason="stop")

    assert await finish_with_details(db_session, request_id, record)

    row = await saved(db_session, request_id)
    assert (row.cached_tokens, row.cache_write_tokens, row.reasoning_tokens) == (
        4,
        None,
        1,
    )
    assert row.finish_reason == "stop"
    assert row.status == R.SUCCESS


async def test_a_failure_keeps_its_user_message_and_http_status(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    record = to_slot_record(failed(R.FAILED), None)
    record = record.__class__(
        **{**record.__dict__, "http_status": 429, "error_message": "잠시 후 다시 시도"}
    )

    assert await finish_with_details(db_session, request_id, record)

    row = await saved(db_session, request_id)
    assert (row.error_message, row.http_status) == ("잠시 후 다시 시도", 429)


async def test_details_are_not_written_to_a_cancelled_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    assert await cancel_request(db_session, request_id, END)

    assert not await save_finish_details(
        db_session, request_id, success_record(finish_reason="stop")
    )

    row = await saved(db_session, request_id)
    assert (row.status, row.finish_reason) == (R.CANCELLED, None)


async def test_details_are_not_written_when_the_status_differs_from_the_record(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    assert await finish_with_details(db_session, request_id, success_record())

    failed_record = to_slot_record(failed(R.FAILED), None)
    assert not await save_finish_details(db_session, request_id, failed_record)

    assert (await saved(db_session, request_id)).error_message is None


# --- 재시작 복구 ---


@pytest.mark.parametrize("started", [False, True])
async def test_unfinished_requests_are_failed_with_unknown_cost(
    factory: Factory, db_session: AsyncSession, started: bool
) -> None:
    request_id = (
        await running(factory, db_session)
        if started
        else await pending(factory, db_session)
    )

    assert await fail_unfinished_simulation_request(db_session, request_id, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)
    assert row.error_message is not None
    # 호출 중이던 요청은 이미 과금됐을 수 있다. 0 으로 닫지 않는다
    assert (row.cost_status, row.cost_usd) == (CostStatus.UNKNOWN, None)
    assert row.completed_at == END


async def test_recovery_does_not_touch_a_request_that_already_ended(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    assert await cancel_request(db_session, request_id, END)

    assert not await fail_unfinished_simulation_request(db_session, request_id, END)

    assert (await saved(db_session, request_id)).status == R.CANCELLED


async def test_call_status_values_match_the_database_values() -> None:
    # 호출 결과 상태(openrouter)와 DB 상태는 이름이 같아야 그대로 옮길 수 있다
    assert {s.value for s in CallStatus} <= {s.value for s in RequestStatus}

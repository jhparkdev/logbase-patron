import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    AIRequestPayload,
    CallPurpose,
    CostSource,
    CostStatus,
    DataSource,
    ErrorType,
    RequestStatus,
    UsageOrigin,
)
from app.openrouter.result import CallStatus
from app.services.requests import (
    cancel_simulation_request,
    create_simulation_request,
    fail_unfinished_simulation_request,
    finish_simulation_request,
    save_simulation_payload,
    start_simulation_request,
)
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_ports import NewRequest, SlotRecord
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
    await create_simulation_request(session, request)
    return request.request_id


async def running(factory: Factory, session: AsyncSession) -> uuid.UUID:
    request_id = await pending(factory, session)
    assert await start_simulation_request(session, request_id)
    return request_id


def success_record(**overrides: Any) -> SlotRecord:
    record = to_slot_record(ok('{"title": "a"}'), None)
    return record.__class__(**{**record.__dict__, **overrides})


# --- 만들기 ---


async def test_a_request_is_created_pending_with_unknown_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    request = await new_request(factory)

    await create_simulation_request(db_session, request)

    row = await saved(db_session, request.request_id)
    assert row.status == R.PENDING
    # 비용은 아직 모른다. 0 이 아니라 null 이다
    assert (row.cost_status, row.cost_usd) == (CostStatus.UNKNOWN, None)
    assert row.usage_origin == UsageOrigin.SIMULATION
    assert row.call_purpose == CallPurpose.EXPERIMENT
    assert row.simulation_id == request.simulation_id
    assert (row.project_id, row.key_id, row.service_id) == (
        request.project_id,
        request.key_id,
        request.service_id,
    )
    assert row.customer_id is None  # 시뮬레이터 호출은 고객에 귀속하지 않는다
    assert row.executed_by == request.executed_by
    assert (row.requested_model, row.requested_provider) == (
        request.requested_model,
        "DeepInfra",
    )
    assert row.routing_policy == {"allow_fallbacks": False, "order": ["DeepInfra"]}
    assert row.execution_config == {"max_tokens": 4096}
    assert row.input_hash == "a" * 64
    assert (row.requested_at, row.completed_at) == (T0, None)
    assert row.data_source == DataSource.LIVE


# --- 시작 ---


async def test_start_moves_pending_to_running_once(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await pending(factory, db_session)

    assert await start_simulation_request(db_session, request_id)
    assert not await start_simulation_request(db_session, request_id)

    assert (await saved(db_session, request_id)).status == R.RUNNING


async def test_a_cancelled_request_is_never_started(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await pending(factory, db_session)
    assert await cancel_simulation_request(db_session, request_id, START)

    assert not await start_simulation_request(db_session, request_id)

    assert (await saved(db_session, request_id)).status == R.CANCELLED


async def test_an_unknown_request_cannot_be_started(db_session: AsyncSession) -> None:
    assert not await start_simulation_request(db_session, uuid.uuid4())


# --- 종료 기록 ---


async def test_a_successful_call_is_recorded_with_tokens_and_confirmed_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    record = success_record(
        cost_usd=Decimal("0.000000348"),
        cached_tokens=4,
        reasoning_tokens=1,
        finish_reason="stop",
    )

    assert await finish_simulation_request(db_session, request_id, record, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type, row.error_message) == (R.SUCCESS, None, None)
    assert (row.input_tokens, row.output_tokens) == (10, 5)
    assert (row.cached_tokens, row.cache_write_tokens, row.reasoning_tokens) == (
        4,
        None,
        1,
    )
    assert row.cost_usd == Decimal("0.000000348")
    assert (row.cost_status, row.cost_source) == (
        CostStatus.CONFIRMED,
        CostSource.API_RESPONSE,
    )
    assert row.cost_confirmed_at == END
    assert (row.actual_provider, row.actual_model) == ("P", "m")
    assert row.external_generation_id == "gen"
    assert (row.latency_ms, row.finish_reason, row.http_status) == (100, "stop", None)
    assert row.completed_at == END


async def test_a_failed_call_keeps_its_error_and_stays_unknown_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    record = to_slot_record(failed(R.FAILED), None)

    assert await finish_simulation_request(db_session, request_id, record, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)
    assert (row.cost_status, row.cost_usd, row.cost_source) == (
        CostStatus.UNKNOWN,
        None,
        None,
    )
    assert row.cost_confirmed_at is None


async def test_a_zero_cost_that_was_confirmed_is_kept_as_zero(
    factory: Factory, db_session: AsyncSession
) -> None:
    # 무료 모델처럼 확정된 0 USD 는 미확인(null)과 다르다
    request_id = await running(factory, db_session)

    assert await finish_simulation_request(
        db_session, request_id, success_record(cost_usd=Decimal(0)), END
    )

    row = await saved(db_session, request_id)
    assert (row.cost_status, row.cost_usd) == (CostStatus.CONFIRMED, Decimal(0))


async def test_a_finished_request_is_never_rewritten(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    assert await finish_simulation_request(
        db_session, request_id, success_record(), END
    )

    second = to_slot_record(failed(R.FAILED), None)
    assert not await finish_simulation_request(
        db_session, request_id, second, END + timedelta(seconds=9)
    )

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type, row.completed_at) == (R.SUCCESS, None, END)
    assert row.cost_status == CostStatus.CONFIRMED


async def test_a_request_that_never_started_cannot_be_finished(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await pending(factory, db_session)

    assert not await finish_simulation_request(
        db_session, request_id, success_record(), END
    )

    row = await saved(db_session, request_id)
    assert (row.status, row.cost_usd) == (R.PENDING, None)


# --- 취소 ---


@pytest.mark.parametrize("started", [False, True])
async def test_cancel_closes_an_open_request_with_unknown_cost(
    factory: Factory, db_session: AsyncSession, started: bool
) -> None:
    request_id = (
        await running(factory, db_session)
        if started
        else await pending(factory, db_session)
    )

    assert await cancel_simulation_request(db_session, request_id, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type) == (R.CANCELLED, None)
    # 취소해도 업체 쪽 처리 비용이 나갈 수 있다. 0 으로 두지 않고 미확인으로 둔다
    assert (row.cost_status, row.cost_usd) == (CostStatus.UNKNOWN, None)
    assert row.completed_at == END


async def test_cancelling_twice_changes_nothing_the_second_time(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    assert await cancel_simulation_request(db_session, request_id, END)

    assert not await cancel_simulation_request(
        db_session, request_id, END + timedelta(seconds=9)
    )

    assert (await saved(db_session, request_id)).completed_at == END


async def test_cancel_does_not_touch_a_finished_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    assert await finish_simulation_request(
        db_session, request_id, success_record(), END
    )

    assert not await cancel_simulation_request(db_session, request_id, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.cost_status) == (R.SUCCESS, CostStatus.CONFIRMED)


# --- 같은 칸에 취소와 완료가 함께 온 경우: 먼저 도착한 쪽만 인정 ---


async def test_when_the_result_arrives_first_the_cancel_is_refused(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)

    finished = await finish_simulation_request(
        db_session, request_id, success_record(), END
    )
    cancelled = await cancel_simulation_request(db_session, request_id, END)

    assert (finished, cancelled) == (True, False)
    assert (await saved(db_session, request_id)).status == R.SUCCESS


async def test_when_the_cancel_arrives_first_the_late_result_is_not_saved(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)

    cancelled = await cancel_simulation_request(db_session, request_id, END)
    finished = await finish_simulation_request(
        db_session, request_id, success_record(), END
    )

    assert (cancelled, finished) == (True, False)
    row = await saved(db_session, request_id)
    assert (row.status, row.cost_usd, row.input_tokens) == (R.CANCELLED, None, None)


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
    assert await cancel_simulation_request(db_session, request_id, END)

    assert not await fail_unfinished_simulation_request(db_session, request_id, END)

    assert (await saved(db_session, request_id)).status == R.CANCELLED


# --- 원문 ---


async def payload_of(session: AsyncSession, request_id: uuid.UUID) -> AIRequestPayload:
    row = await session.scalar(
        select(AIRequestPayload).where(AIRequestPayload.request_id == request_id)
    )
    assert row is not None
    return row


async def test_prompt_and_response_text_are_saved_for_the_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)

    await save_simulation_payload(db_session, request_id, MESSAGES, "응답 원문")

    row = await payload_of(db_session, request_id)
    assert row.request_messages == MESSAGES
    assert row.response_text == "응답 원문"


async def test_a_call_without_a_response_still_keeps_its_prompt(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)

    await save_simulation_payload(db_session, request_id, MESSAGES, None)

    row = await payload_of(db_session, request_id)
    assert (row.request_messages, row.response_text) == (MESSAGES, None)


async def test_a_saved_payload_is_not_overwritten(
    factory: Factory, db_session: AsyncSession
) -> None:
    request_id = await running(factory, db_session)
    await save_simulation_payload(db_session, request_id, MESSAGES, "처음 응답")

    await save_simulation_payload(db_session, request_id, MESSAGES, "다른 응답")

    assert (await payload_of(db_session, request_id)).response_text == "처음 응답"


async def test_call_status_values_match_the_database_values() -> None:
    # 정욱님 호출 결과 상태와 DB 상태는 이름이 같아야 그대로 옮길 수 있다
    assert {s.value for s in CallStatus} <= {s.value for s in RequestStatus}

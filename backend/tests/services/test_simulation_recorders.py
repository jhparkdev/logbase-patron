import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from app.services.requests import create_pending
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_recorders import (
    ScopedRequestRecorder,
    SessionRequestRecorder,
)
from tests.db_helpers import T0, Factory
from tests.services.simulation_fakes import failed, ok
from tests.services.test_simulation_requests import (
    MESSAGES,
    new_request,
    saved,
    success_record,
)

R = RequestStatus
END = T0 + timedelta(seconds=5)


class CountingSessions:
    """세션을 몇 번 열었는지 세는 sessionmaker 대역. 실제 세션은 테스트 연결 위에서 열린다."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self.opened = 0

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        self.opened += 1
        async with self._sessions.begin() as session:
            yield session


@pytest.fixture
def sessions(db_session: AsyncSession) -> CountingSessions:
    # 테스트 연결 위에서 세션을 열어, 바깥 트랜잭션을 롤백하면 모두 사라지게 한다
    return CountingSessions(
        async_sessionmaker(
            bind=db_session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
    )


async def status_of(session: AsyncSession, request_id: uuid.UUID) -> RequestStatus:
    row = await session.get(AIRequest, request_id)
    assert row is not None
    await session.refresh(row)
    return RequestStatus(row.status)


# --- 접수용: 요청 세션을 그대로 쓰고 commit 하지 않는다 ---


async def test_session_recorder_writes_in_the_given_session_without_committing(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)

    await recorder.create_pending(request)

    assert await status_of(db_session, request.request_id) == R.PENDING
    assert db_session.in_transaction()  # 닫지도 commit 하지도 않았다


async def test_session_recorder_runs_the_whole_life_of_a_call(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)

    assert await recorder.mark_running(request.request_id, T0)
    assert not await recorder.mark_running(request.request_id, T0)
    record = to_slot_record(ok("응답"), None)
    assert await recorder.record_finished(request.request_id, record, END)
    await recorder.save_payload(request.request_id, MESSAGES, "응답")

    assert await status_of(db_session, request.request_id) == R.SUCCESS


async def test_session_recorder_refuses_a_second_outcome(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)
    await recorder.mark_running(request.request_id, T0)

    assert await recorder.cancel_if_open(request.request_id, END)
    record = to_slot_record(ok("늦은 응답"), None)
    assert not await recorder.record_finished(request.request_id, record, END)

    assert await status_of(db_session, request.request_id) == R.CANCELLED


async def test_a_late_result_after_cancel_is_kept_only_for_reconciliation(
    factory: Factory, db_session: AsyncSession
) -> None:
    # 취소 뒤 도착한 결과는 호출 ID 와 원문만 남기고 상태·비용·토큰은 바꾸지 않는다(J-03)
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)
    await recorder.mark_running(request.request_id, T0)
    assert await recorder.cancel_if_open(request.request_id, END)
    record = to_slot_record(ok("늦은 응답", generation_id="gen-late"), None)

    await recorder.keep_late_result(request.request_id, MESSAGES, record)

    row = await saved(db_session, request.request_id)
    assert (row.status, row.external_generation_id) == (R.CANCELLED, "gen-late")
    assert (row.cost_status, row.cost_usd, row.output_tokens) == (
        CostStatus.UNKNOWN,
        None,
        None,
    )
    payload = await db_session.get(AIRequestPayload, request.request_id)
    assert payload is not None
    assert payload.response_text == "늦은 응답"


async def test_a_late_result_is_not_kept_for_a_call_that_was_not_cancelled(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)
    await recorder.mark_running(request.request_id, T0)
    record = to_slot_record(ok("응답", generation_id="gen"), None)

    await recorder.keep_late_result(request.request_id, MESSAGES, record)

    assert await db_session.get(AIRequestPayload, request.request_id) is None
    assert (await saved(db_session, request.request_id)).external_generation_id is None


# --- 백그라운드용: 호출마다 새 세션을 열고 commit 한다 ---


async def test_scoped_recorder_opens_a_new_session_for_every_write(
    factory: Factory, db_session: AsyncSession, sessions: CountingSessions
) -> None:
    request = await new_request(factory)
    await create_pending(db_session, request)
    recorder = ScopedRequestRecorder(sessions)  # type: ignore[arg-type]

    assert await recorder.mark_running(request.request_id, T0)
    record = to_slot_record(ok("응답"), None)
    assert await recorder.record_finished(request.request_id, record, END)
    await recorder.save_payload(request.request_id, MESSAGES, "응답")

    # 동시에 도는 여러 칸이 한 세션을 함께 쓰지 않도록 쓸 때마다 새로 연다
    assert sessions.opened == 3
    assert await status_of(db_session, request.request_id) == R.SUCCESS


async def test_scoped_recorder_reports_whether_the_write_won(
    factory: Factory, db_session: AsyncSession, sessions: CountingSessions
) -> None:
    request = await new_request(factory)
    await create_pending(db_session, request)
    recorder = ScopedRequestRecorder(sessions)  # type: ignore[arg-type]
    await recorder.mark_running(request.request_id, T0)

    assert await recorder.cancel_if_open(request.request_id, END)
    assert not await recorder.cancel_if_open(request.request_id, END)

    row = await db_session.get(AIRequest, request.request_id)
    assert row is not None
    await db_session.refresh(row)
    assert (row.status, row.cost_status, row.cost_usd) == (
        R.CANCELLED,
        CostStatus.UNKNOWN,
        None,
    )


async def test_scoped_recorder_does_not_start_a_cancelled_call(
    factory: Factory, db_session: AsyncSession, sessions: CountingSessions
) -> None:
    request = await new_request(factory)
    await create_pending(db_session, request)
    recorder = ScopedRequestRecorder(sessions)  # type: ignore[arg-type]
    await recorder.cancel_if_open(request.request_id, END)

    assert not await recorder.mark_running(request.request_id, END)


# --- 호출 이력 한 건의 기록 계약 (접수용 recorder 로 검증) ---


async def started(
    factory: Factory, session: AsyncSession
) -> tuple[SessionRequestRecorder, uuid.UUID]:
    recorder = SessionRequestRecorder(session)
    request = await new_request(factory)
    await recorder.create_pending(request)
    assert await recorder.mark_running(request.request_id, T0)
    return recorder, request.request_id


async def test_a_request_is_created_pending_with_unknown_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    request = await new_request(factory)

    await SessionRequestRecorder(db_session).create_pending(request)

    row = await saved(db_session, request.request_id)
    assert row.status == R.PENDING
    # 비용은 아직 모른다. 0 이 아니라 null 이다
    assert (row.cost_status, row.cost_usd) == (CostStatus.UNKNOWN, None)
    assert (row.usage_origin, row.call_purpose) == (
        UsageOrigin.SIMULATION,
        CallPurpose.EXPERIMENT,
    )
    assert row.simulation_id == request.simulation_id
    assert (row.project_id, row.key_id, row.service_id) == (
        request.project_id,
        request.key_id,
        request.service_id,
    )
    assert row.customer_id is None  # 시뮬레이터 호출은 고객에 귀속하지 않는다
    assert row.routing_policy == {"allow_fallbacks": False, "order": ["DeepInfra"]}
    assert row.execution_config == {"max_tokens": 4096}
    assert (row.requested_at, row.completed_at) == (T0, None)
    assert row.data_source == DataSource.LIVE


async def test_a_cancelled_request_is_never_started(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)
    assert await recorder.cancel_if_open(request.request_id, END)

    assert not await recorder.mark_running(request.request_id, END)

    assert await status_of(db_session, request.request_id) == R.CANCELLED


async def test_a_successful_call_is_recorded_with_tokens_details_and_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)
    record = success_record(
        cost_usd=Decimal("0.000000348"),
        cached_tokens=4,
        reasoning_tokens=1,
        finish_reason="stop",
    )

    assert await recorder.record_finished(request_id, record, END)

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
    assert (row.latency_ms, row.finish_reason, row.completed_at) == (100, "stop", END)


async def test_a_failed_call_keeps_its_error_and_stays_unknown_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)
    record = to_slot_record(failed(R.FAILED), None)
    record = record.__class__(
        **{**record.__dict__, "error_message": "잠시 후 다시 시도", "http_status": 503}
    )

    assert await recorder.record_finished(request_id, record, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)
    assert (row.error_message, row.http_status) == ("잠시 후 다시 시도", 503)
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
    recorder, request_id = await started(factory, db_session)

    assert await recorder.record_finished(
        request_id, success_record(cost_usd=Decimal(0)), END
    )

    row = await saved(db_session, request_id)
    assert (row.cost_status, row.cost_usd) == (CostStatus.CONFIRMED, Decimal(0))


async def test_a_finished_request_is_never_rewritten(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)
    assert await recorder.record_finished(request_id, success_record(), END)

    second = to_slot_record(failed(R.FAILED), None)
    later = END + timedelta(seconds=9)
    assert not await recorder.record_finished(request_id, second, later)

    row = await saved(db_session, request_id)
    assert (row.status, row.error_type, row.completed_at) == (R.SUCCESS, None, END)
    assert (row.error_message, row.cost_status) == (None, CostStatus.CONFIRMED)


async def test_a_request_that_never_started_cannot_be_finished(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)

    assert not await recorder.record_finished(
        request.request_id, success_record(finish_reason="stop"), END
    )

    row = await saved(db_session, request.request_id)
    assert (row.status, row.cost_usd, row.finish_reason) == (R.PENDING, None, None)


@pytest.mark.parametrize("run_first", [False, True])
async def test_cancel_closes_an_open_request_with_unknown_cost(
    factory: Factory, db_session: AsyncSession, run_first: bool
) -> None:
    recorder = SessionRequestRecorder(db_session)
    request = await new_request(factory)
    await recorder.create_pending(request)
    if run_first:
        await recorder.mark_running(request.request_id, T0)

    assert await recorder.cancel_if_open(request.request_id, END)

    row = await saved(db_session, request.request_id)
    assert (row.status, row.error_type) == (R.CANCELLED, None)
    # 취소해도 업체 쪽 처리 비용이 나갈 수 있다. 0 으로 두지 않고 미확인으로 둔다
    assert (row.cost_status, row.cost_usd) == (CostStatus.UNKNOWN, None)
    assert row.completed_at == END


async def test_cancel_does_not_touch_a_finished_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)
    assert await recorder.record_finished(request_id, success_record(), END)

    assert not await recorder.cancel_if_open(request_id, END)

    row = await saved(db_session, request_id)
    assert (row.status, row.cost_status) == (R.SUCCESS, CostStatus.CONFIRMED)


async def test_a_late_result_after_cancel_leaves_no_trace(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)
    assert await recorder.cancel_if_open(request_id, END)

    assert not await recorder.record_finished(
        request_id, success_record(finish_reason="stop"), END
    )

    row = await saved(db_session, request_id)
    assert (row.status, row.cost_usd, row.input_tokens, row.finish_reason) == (
        R.CANCELLED,
        None,
        None,
        None,
    )


async def payload_of(session: AsyncSession, request_id: uuid.UUID) -> AIRequestPayload:
    row = await session.scalar(
        select(AIRequestPayload).where(AIRequestPayload.request_id == request_id)
    )
    assert row is not None
    return row


async def test_prompt_and_response_text_are_saved_for_the_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)

    await recorder.save_payload(request_id, MESSAGES, "응답 원문")

    row = await payload_of(db_session, request_id)
    assert (row.request_messages, row.response_text) == (MESSAGES, "응답 원문")


async def test_a_call_without_a_response_still_keeps_its_prompt(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)

    await recorder.save_payload(request_id, MESSAGES, None)

    row = await payload_of(db_session, request_id)
    assert (row.request_messages, row.response_text) == (MESSAGES, None)


async def test_a_saved_payload_is_rejected_the_second_time_and_kept(
    factory: Factory, db_session: AsyncSession
) -> None:
    recorder, request_id = await started(factory, db_session)
    await recorder.save_payload(request_id, MESSAGES, "처음 응답")

    # 원문은 한 번만 저장한다. 중복은 조용히 넘기지 않고 DB 오류로 알린다
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await recorder.save_payload(request_id, MESSAGES, "다른 응답")

    assert (await payload_of(db_session, request_id)).response_text == "처음 응답"

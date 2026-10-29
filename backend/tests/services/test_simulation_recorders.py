import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AIRequest, CostStatus, RequestStatus
from app.services.requests import create_simulation_request
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_recorders import (
    ScopedRequestRecorder,
    SessionRequestRecorder,
)
from tests.db_helpers import T0, Factory
from tests.services.simulation_fakes import ok
from tests.services.test_requests import MESSAGES, new_request

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


# --- 백그라운드용: 호출마다 새 세션을 열고 commit 한다 ---


async def test_scoped_recorder_opens_a_new_session_for_every_write(
    factory: Factory, db_session: AsyncSession, sessions: CountingSessions
) -> None:
    request = await new_request(factory)
    await create_simulation_request(db_session, request)
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
    await create_simulation_request(db_session, request)
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
    await create_simulation_request(db_session, request)
    recorder = ScopedRequestRecorder(sessions)  # type: ignore[arg-type]
    await recorder.cancel_if_open(request.request_id, END)

    assert not await recorder.mark_running(request.request_id, END)

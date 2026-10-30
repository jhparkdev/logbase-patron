"""미완료 실행 복구(J-01)와 취소 후 정리(J-03) 테스트.

판단 함수는 현재 시각을 받아 DB 없이 경계를 검사하고, 정리 작업은 patron_test DB 로 검사한다.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    CostStatus,
    ErrorType,
    RequestStatus,
    SimulationRun,
    SimulationStatus,
)
from app.services.simulation_input import SIMULATION_TIMEOUT_SECONDS
from app.services.simulation_recovery import (
    CANCEL_SETTLE_SECONDS,
    is_call_overdue,
    recover_unfinished,
    run_status_to_close,
)
from tests.db_helpers import T0, Factory

R = RequestStatus
S = SimulationStatus
TIMEOUT = timedelta(seconds=SIMULATION_TIMEOUT_SECONDS)
SETTLE = timedelta(seconds=CANCEL_SETTLE_SECONDS)
TICK = timedelta(microseconds=1)
NEVER_ACTIVE = frozenset[uuid.UUID]()


# --- 호출이 Timeout 을 넘겼는가 (J-01) ---


@pytest.mark.parametrize(
    ("elapsed", "overdue"),
    [(TIMEOUT - TICK, False), (TIMEOUT, False), (TIMEOUT + TICK, True)],
    ids=["just-before", "exactly", "just-after"],
)
def test_a_call_is_overdue_only_after_the_timeout(
    elapsed: timedelta, overdue: bool
) -> None:
    assert is_call_overdue(T0, T0 + elapsed) is overdue


def test_the_timeout_is_the_simulation_call_timeout() -> None:
    assert SIMULATION_TIMEOUT_SECONDS == 180


# --- 실행 전체를 닫을 수 있는가 (J-01 확정, J-03 강제 확정) ---


def test_a_run_with_an_open_call_is_not_closed() -> None:
    assert (
        run_status_to_close([R.SUCCESS, R.RUNNING], T0, T0, task_active=False) is None
    )


def test_a_run_nobody_is_running_is_closed_with_its_overall_status() -> None:
    # 서버가 다시 떠서 실행 작업이 없다. 칸이 다 끝났으면 기다릴 이유가 없다
    status = run_status_to_close([R.SUCCESS, R.CANCELLED], T0, T0, task_active=False)

    assert status == S.PARTIAL_SUCCESS


@pytest.mark.parametrize(
    ("elapsed", "closed"),
    [(SETTLE - TICK, False), (SETTLE, False), (SETTLE + TICK, True)],
    ids=["just-before", "exactly", "just-after"],
)
def test_a_running_task_gets_time_to_close_its_own_run(
    elapsed: timedelta, closed: bool
) -> None:
    # 취소 뒤 칸이 다 끝났는데도 작업이 실행을 닫지 못하고 있으면 정해진 시간 뒤 강제로 닫는다
    status = run_status_to_close(
        [R.CANCELLED, R.CANCELLED], T0, T0 + elapsed, task_active=True
    )

    assert status == (S.CANCELLED if closed else None)


def test_a_run_without_slots_is_left_alone() -> None:
    assert run_status_to_close([], None, T0, task_active=False) is None


# --- 정리 작업 (DB) ---


async def open_run(factory: Factory, **values: Any) -> uuid.UUID:
    row = await factory.simulation_run(status="RUNNING", started_at=T0, **values)
    return row["simulation_id"]


async def slot(
    factory: Factory, simulation_id: uuid.UUID, slot_no: int, **request: Any
) -> uuid.UUID:
    row = await factory.ai_request(
        usage_origin="SIMULATION", simulation_id=simulation_id, **request
    )
    await factory.simulation_result(
        simulation_id=simulation_id, request_id=row["request_id"], slot_no=slot_no
    )
    return row["request_id"]


async def request_row(session: AsyncSession, request_id: uuid.UUID) -> AIRequest:
    row = await session.scalar(
        select(AIRequest)
        .where(AIRequest.request_id == request_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def run_row(session: AsyncSession, simulation_id: uuid.UUID) -> SimulationRun:
    row = await session.scalar(
        select(SimulationRun)
        .where(SimulationRun.simulation_id == simulation_id)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def test_overdue_calls_fail_with_unknown_cost_and_the_run_is_closed(
    db_session: AsyncSession, factory: Factory
) -> None:
    run = await open_run(factory)
    running = await slot(factory, run, 1, status="RUNNING")
    pending = await slot(factory, run, 2)
    now = T0 + TIMEOUT + TICK

    report = await recover_unfinished(db_session, now, NEVER_ACTIVE.__contains__)

    for request_id in (running, pending):
        row = await request_row(db_session, request_id)
        assert (row.status, row.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)
        # 호출 중이던 요청은 이미 과금됐을 수 있어 0 이 아니라 미확인으로 닫는다
        assert (row.cost_status, row.cost_usd) == (CostStatus.UNKNOWN, None)
    closed = await run_row(db_session, run)
    assert (closed.status, closed.completed_at) == (S.FAILED, now)
    assert (report.failed_calls, report.closed_runs) == (2, 1)


async def test_calls_still_within_the_timeout_are_left_running(
    db_session: AsyncSession, factory: Factory
) -> None:
    run = await open_run(factory)
    request_id = await slot(factory, run, 1, status="RUNNING")

    report = await recover_unfinished(
        db_session, T0 + TIMEOUT, NEVER_ACTIVE.__contains__
    )

    assert (await request_row(db_session, request_id)).status == R.RUNNING
    assert (await run_row(db_session, run)).status == S.RUNNING
    assert (report.failed_calls, report.closed_runs) == (0, 0)


async def test_a_run_this_server_is_still_running_is_not_touched(
    db_session: AsyncSession, factory: Factory
) -> None:
    # 실행 작업이 살아 있으면 호출 Timeout 도 그 작업이 처리한다
    run = await open_run(factory)
    request_id = await slot(factory, run, 1, status="RUNNING")

    await recover_unfinished(db_session, T0 + TIMEOUT + TICK, {run}.__contains__)

    assert (await request_row(db_session, request_id)).status == R.RUNNING


async def test_finished_calls_keep_their_results(
    db_session: AsyncSession, factory: Factory
) -> None:
    run = await open_run(factory)
    done = await slot(
        factory,
        run,
        1,
        status="SUCCESS",
        completed_at=T0,
        cost_status="CONFIRMED",
        cost_usd=Decimal("0.001"),
    )
    await slot(factory, run, 2, status="RUNNING")

    await recover_unfinished(db_session, T0 + TIMEOUT + TICK, NEVER_ACTIVE.__contains__)

    row = await request_row(db_session, done)
    assert (row.status, row.cost_usd) == (R.SUCCESS, Decimal("0.001"))
    assert (await run_row(db_session, run)).status == S.PARTIAL_SUCCESS


async def test_a_cancelled_run_left_open_is_closed_after_the_settle_time(
    db_session: AsyncSession, factory: Factory
) -> None:
    # 취소로 칸이 다 끝났는데 실행을 닫던 작업이 멈춘 경우(J-03)
    run = await open_run(factory)
    for slot_no in (1, 2):
        await slot(factory, run, slot_no, status="CANCELLED", completed_at=T0)

    await recover_unfinished(db_session, T0 + SETTLE, {run}.__contains__)
    assert (await run_row(db_session, run)).status == S.RUNNING

    await recover_unfinished(db_session, T0 + SETTLE + TICK, {run}.__contains__)
    assert (await run_row(db_session, run)).status == S.CANCELLED


async def test_finished_runs_are_not_rewritten(
    db_session: AsyncSession, factory: Factory
) -> None:
    run = (await factory.simulation_run(status="SUCCESS", completed_at=T0))[
        "simulation_id"
    ]
    await slot(factory, run, 1, status="SUCCESS", completed_at=T0)

    report = await recover_unfinished(
        db_session, T0 + TIMEOUT + TICK, NEVER_ACTIVE.__contains__
    )

    closed = await run_row(db_session, run)
    assert (closed.status, closed.completed_at) == (S.SUCCESS, T0)
    assert report.closed_runs == 0


async def test_calls_outside_the_simulator_are_not_recovered(
    db_session: AsyncSession, factory: Factory
) -> None:
    # 다른 기능의 호출은 이 작업의 대상이 아니다
    other = await factory.ai_request(status="RUNNING")

    await recover_unfinished(db_session, T0 + TIMEOUT + TICK, NEVER_ACTIVE.__contains__)

    assert (await request_row(db_session, other["request_id"])).status == R.RUNNING

"""미완료 실행 복구(J-01)와 취소 후 정리(J-03). 서버 시작 때와 주기적으로 돈다(app/main.py lifespan).

- J-01: Timeout 을 넘긴 PENDING·RUNNING 시뮬레이터 호출을 실패 + 비용 미확인으로 닫는다.
- J-03: 취소는 요청 즉시 호출을 CANCELLED 로 기록한다(simulation_cancel_service.py). 그래서 여기서는
  칸이 모두 끝났는데 실행이 열려 있으면 전체 상태를 확정한다. 실행 작업이 살아 있으면 스스로 닫을
  시간을 주고, 그래도 닫지 못하면 강제로 닫는다.
이 서버에서 돌고 있는 실행의 호출은 그 작업이 Timeout 까지 처리하므로 건드리지 않는다.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AIRequest,
    RequestStatus,
    SimulationResult,
    SimulationRun,
    SimulationStatus,
    UsageOrigin,
)
from app.services.simulation_input import SIMULATION_TIMEOUT_SECONDS
from app.services.simulation_requests import fail_unfinished_simulation_request
from app.services.simulation_status import compute_overall_status, is_run_finished
from app.services.simulation_store import DbSimulationStore

# 로그에는 건수와 예외 종류만 남긴다
logger = logging.getLogger(__name__)

RECOVERY_INTERVAL_SECONDS = 60
# 칸이 모두 끝난 뒤 실행 작업이 실행을 닫는 데는 보통 1초도 걸리지 않는다. 넉넉히 기다린 뒤 강제로 닫는다
CANCEL_SETTLE_SECONDS = 30

_OPEN_CALLS = (RequestStatus.PENDING, RequestStatus.RUNNING)
_OPEN_RUNS = (SimulationStatus.PENDING, SimulationStatus.RUNNING)


@dataclass(frozen=True)
class RecoveryReport:
    failed_calls: int
    closed_runs: int


def is_call_overdue(
    requested_at: datetime,
    now: datetime,
    timeout_seconds: float = SIMULATION_TIMEOUT_SECONDS,
) -> bool:
    """호출이 Timeout 을 넘겼는가. 정확히 Timeout 인 순간은 아직 넘기지 않은 것으로 본다."""
    return now - requested_at > timedelta(seconds=timeout_seconds)


def run_status_to_close(
    statuses: Sequence[RequestStatus],
    last_completed_at: datetime | None,
    now: datetime,
    *,
    task_active: bool,
    settle_seconds: float = CANCEL_SETTLE_SECONDS,
) -> SimulationStatus | None:
    """열려 있는 실행을 지금 닫아야 하면 그 전체 상태를, 아니면 None 을 돌려준다."""
    if not statuses:
        return None
    overall = compute_overall_status(statuses)
    if not is_run_finished(overall):
        return None
    if not task_active:
        return overall
    if last_completed_at is None:
        return None
    waited = now - last_completed_at > timedelta(seconds=settle_seconds)
    return overall if waited else None


async def recover_unfinished(
    session: AsyncSession, now: datetime, is_active: Callable[[uuid.UUID], bool]
) -> RecoveryReport:
    """J-01·J-03 을 한 번 수행한다. commit 은 부르는 쪽이 한다."""
    failed = 0
    for request_id, simulation_id, requested_at in await _open_calls(session):
        if is_active(simulation_id) or not is_call_overdue(requested_at, now):
            continue
        if await fail_unfinished_simulation_request(session, request_id, now):
            failed += 1

    closed = 0
    store = DbSimulationStore(session)
    for simulation_id in await _open_runs(session):
        slots = await _final_slots(session, simulation_id)
        status = run_status_to_close(
            [s for s, _ in slots],
            max((at for _, at in slots if at is not None), default=None),
            now,
            task_active=is_active(simulation_id),
        )
        if status is not None:
            await store.mark_finished(simulation_id, status, now)
            closed += 1
    return RecoveryReport(failed_calls=failed, closed_runs=closed)


async def run_recovery_loop(
    sessions: async_sessionmaker[AsyncSession],
    is_active: Callable[[uuid.UUID], bool],
    *,
    interval_seconds: float = RECOVERY_INTERVAL_SECONDS,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """서버가 떠 있는 동안 바로 한 번, 그 뒤 주기마다 정리한다. 실패해도 다음 주기에 다시 한다."""
    while True:
        try:
            async with sessions.begin() as session:
                report = await recover_unfinished(session, now(), is_active)
            if report.failed_calls or report.closed_runs:
                logger.info(
                    "simulation recovery: failed_calls=%s closed_runs=%s",
                    report.failed_calls,
                    report.closed_runs,
                )
        except Exception as error:  # noqa: BLE001 - 정리 실패로 서버가 멈추지 않게 하고 다음 주기에 다시 한다
            logger.error("simulation recovery failed: error=%s", type(error).__name__)
        await asyncio.sleep(interval_seconds)


async def _open_calls(
    session: AsyncSession,
) -> list[tuple[uuid.UUID, uuid.UUID, datetime]]:
    rows = await session.execute(
        select(AIRequest.request_id, AIRequest.simulation_id, AIRequest.requested_at)
        .where(
            AIRequest.usage_origin == UsageOrigin.SIMULATION,
            AIRequest.simulation_id.is_not(None),
            AIRequest.status.in_(_OPEN_CALLS),
        )
        .order_by(AIRequest.requested_at)
    )
    return [(r.request_id, r.simulation_id, r.requested_at) for r in rows]


async def _open_runs(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(SimulationRun.simulation_id).where(SimulationRun.status.in_(_OPEN_RUNS))
    )
    return list(rows)


async def _final_slots(
    session: AsyncSession, simulation_id: uuid.UUID
) -> list[tuple[RequestStatus, datetime | None]]:
    rows = await session.execute(
        select(AIRequest.status, AIRequest.completed_at)
        .join(SimulationResult, SimulationResult.request_id == AIRequest.request_id)
        .where(
            SimulationResult.simulation_id == simulation_id,
            SimulationResult.is_final_attempt,
        )
    )
    return [(RequestStatus(status), completed_at) for status, completed_at in rows]

"""POST /api/simulations/{id}/cancel (S-07), /slots/{n}/cancel (S-06) 테스트.

실제 작업 관리자와 DB 로 돌리고 모델 호출만 가짜로 둔다. 가짜 호출은 취소 신호가 켜질 때까지 기다린다.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.simulation_deps import get_cancel_deps, get_simulation_manager
from app.models import (
    AIRequest,
    CostStatus,
    RequestStatus,
    SimulationResult,
    SimulationRun,
    SimulationStatus,
)
from app.services.simulation_cancel_service import CancelDeps
from app.services.simulation_manager import SimulationManager
from app.services.simulation_recorders import ScopedRequestRecorder
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_scoped_store import ScopedSimulationStore
from tests.api.simulation_helpers import (
    CREATE,
    SerializedSessions,
    build_manager,
    build_sessions,
    create_body,
)
from tests.db_helpers import T0, Factory
from tests.services.simulation_fakes import FakeCaller, until_cancelled

R = RequestStatus
S = SimulationStatus
CANCEL_TIME = T0 + timedelta(seconds=7)


class RecordingRecorder(ScopedRequestRecorder):
    """취소를 DB 에 확정(commit)한 직후에 "cancelled" 를 남긴다.

    cancel_if_open 은 세션을 열어 쓰고 닫은 뒤에 돌아오므로, 이 표시는 commit 이 끝난 뒤에 찍힌다.
    """

    def __init__(self, sessions: SerializedSessions, log: list[str]) -> None:
        super().__init__(sessions)  # type: ignore[arg-type]
        self._log = log

    async def cancel_if_open(self, request_id: uuid.UUID, now: datetime) -> bool:
        cancelled = await super().cancel_if_open(request_id, now)
        if cancelled:
            self._log.append("cancelled")
        return cancelled


class RecordingRegistry(CancelRegistry):
    """멈춤 신호가 켜질 때마다 events 에 "signal" 을 남긴다."""

    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self._log = log

    def signal(self, request_id: uuid.UUID) -> None:
        self._log.append("signal")
        super().signal(request_id)


@dataclass
class CancelEnv:
    sessions: SerializedSessions
    registry: RecordingRegistry
    events: list[str]


@pytest.fixture(autouse=True)
def cancel_env(app: FastAPI, db_session: AsyncSession) -> CancelEnv:
    """취소 경로가 테스트 DB 연결과 같은 취소 신호 보관함을 쓰게 한다. 모델 호출기는 필요 없다."""
    events: list[str] = []
    sessions = build_sessions(db_session)
    registry = RecordingRegistry(events)
    deps = CancelDeps(
        store=ScopedSimulationStore(sessions),  # type: ignore[arg-type]
        recorder=RecordingRecorder(sessions, events),
        registry=registry,
        now=lambda: CANCEL_TIME,
    )
    app.dependency_overrides[get_cancel_deps] = lambda: deps
    return CancelEnv(sessions, registry, events)


@dataclass
class Running:
    simulation_id: uuid.UUID
    request_ids: list[uuid.UUID]
    manager: SimulationManager


@pytest.fixture
async def running(
    app: FastAPI,
    client: AsyncClient,
    factory: Factory,
    db_session: AsyncSession,
    cancel_env: CancelEnv,
    poc_setup: None,
    signed_in: dict[str, Any],
) -> Running:
    """모델 2개가 모두 응답을 기다리며 돌고 있는 실행."""
    rows = [dict(await factory.model(status="ACTIVE")) for _ in range(2)]
    started = [asyncio.Event(), asyncio.Event()]
    caller = FakeCaller(
        {
            row["openrouter_model_id"]: until_cancelled(started[n])
            for n, row in enumerate(rows)
        }
    )
    manager = build_manager(
        db_session,
        caller,
        registry=cancel_env.registry,
        sessions=cancel_env.sessions,
    )
    app.dependency_overrides[get_simulation_manager] = lambda: manager
    response = await client.post(
        CREATE, json=create_body([r["model_id"] for r in rows])
    )
    await asyncio.wait_for(asyncio.gather(*(e.wait() for e in started)), timeout=2)
    simulation_id = uuid.UUID(response.json()["simulation_id"])
    request_ids = list(
        await db_session.scalars(
            select(SimulationResult.request_id)
            .where(SimulationResult.simulation_id == simulation_id)
            .order_by(SimulationResult.slot_no)
        )
    )
    cancel_env.events.clear()
    return Running(simulation_id, request_ids, manager)


def run_url(simulation_id: object) -> str:
    return f"{CREATE}/{simulation_id}/cancel"


def slot_url(simulation_id: object, slot_no: int) -> str:
    return f"{CREATE}/{simulation_id}/slots/{slot_no}/cancel"


async def request_row(session: AsyncSession, request_id: uuid.UUID) -> AIRequest:
    row = await session.get(AIRequest, request_id)
    assert row is not None
    await session.refresh(row)
    return row


# --- 모델 하나 취소 (S-06) ---


async def test_cancelling_one_model_stops_only_that_model(
    client: AsyncClient, running: Running, db_session: AsyncSession
) -> None:
    response = await client.post(slot_url(running.simulation_id, 1))

    assert response.status_code == 200
    assert response.json() == {
        "simulation_id": str(running.simulation_id),
        "status": "RUNNING",  # 나머지 모델이 아직 돌고 있다
        "results": [
            {
                "request_id": str(running.request_ids[0]),
                "slot_no": 1,
                "decision": "CANCEL",
                "status": "CANCELLED",
            }
        ],
    }
    cancelled = await request_row(db_session, running.request_ids[0])
    other = await request_row(db_session, running.request_ids[1])
    assert cancelled.status == R.CANCELLED
    # 취소해도 업체 쪽 비용이 나갔을 수 있다. 0 이 아니라 미확인이다
    assert (cancelled.cost_status, cancelled.cost_usd) == (CostStatus.UNKNOWN, None)
    assert other.status == R.RUNNING
    await client.post(run_url(running.simulation_id))
    await running.manager.wait_idle()


async def test_cancelling_the_same_model_twice_gives_the_same_answer(
    client: AsyncClient, running: Running
) -> None:
    first = await client.post(slot_url(running.simulation_id, 1))
    second = await client.post(slot_url(running.simulation_id, 1))

    assert first.status_code == second.status_code == 200
    assert first.json()["results"][0]["decision"] == "CANCEL"
    assert second.json()["results"][0]["decision"] == "ALREADY_CANCELLED"
    assert second.json()["results"][0]["status"] == "CANCELLED"
    await client.post(run_url(running.simulation_id))
    await running.manager.wait_idle()


# --- 실행 전체 취소 (S-07) ---


async def test_cancelling_the_whole_run_ends_it_as_cancelled(
    client: AsyncClient, running: Running, db_session: AsyncSession
) -> None:
    await client.post(slot_url(running.simulation_id, 1))

    response = await client.post(run_url(running.simulation_id))
    await running.manager.wait_idle()

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "CANCELLED"
    assert [(r["slot_no"], r["decision"], r["status"]) for r in body["results"]] == [
        (1, "ALREADY_CANCELLED", "CANCELLED"),
        (2, "CANCEL", "CANCELLED"),
    ]
    run = await db_session.get(SimulationRun, running.simulation_id)
    assert run is not None
    await db_session.refresh(run)
    # 실행 종료는 돌고 있던 작업이 한 번 기록한다
    assert (run.status, run.completed_at) == (S.CANCELLED, T0 + timedelta(seconds=5))
    assert running.manager.active_count == 0


async def test_the_cancelled_state_is_committed_before_the_call_is_told_to_stop(
    client: AsyncClient, running: Running, cancel_env: CancelEnv
) -> None:
    # 멈춤 신호가 먼저 켜지면 실행 작업이 아직 확정되지 않은 옛 상태를 읽어 실행이 끝나지 못한다
    await client.post(slot_url(running.simulation_id, 1))

    assert cancel_env.events == ["cancelled", "signal"]
    await client.post(run_url(running.simulation_id))
    await running.manager.wait_idle()


async def test_cancelling_a_finished_run_changes_nothing(
    app: FastAPI,
    client: AsyncClient,
    factory: Factory,
    db_session: AsyncSession,
    cancel_env: CancelEnv,
    poc_setup: None,
    signed_in: dict[str, Any],
) -> None:
    rows = [dict(await factory.model(status="ACTIVE")) for _ in range(2)]
    manager = build_manager(
        db_session,
        FakeCaller(),
        registry=cancel_env.registry,
        sessions=cancel_env.sessions,
    )
    app.dependency_overrides[get_simulation_manager] = lambda: manager
    created = await client.post(CREATE, json=create_body([r["model_id"] for r in rows]))
    await manager.wait_idle()
    simulation_id = created.json()["simulation_id"]

    response = await client.post(run_url(simulation_id))

    body = response.json()
    assert response.status_code == 200  # 오류가 아니다. 이미 끝났다고 알려 준다
    assert body["status"] == "SUCCESS"
    assert {r["decision"] for r in body["results"]} == {"ALREADY_TERMINAL"}
    assert {r["status"] for r in body["results"]} == {"SUCCESS"}
    run = await db_session.get(SimulationRun, uuid.UUID(simulation_id))
    assert run is not None
    await db_session.refresh(run)
    assert run.completed_at == T0 + timedelta(seconds=5)  # 다시 쓰이지 않았다


# --- 거절 ---


@pytest.mark.usefixtures("signed_in")
async def test_an_unknown_run_is_404_without_needing_the_model_caller(
    client: AsyncClient,
) -> None:
    whole = await client.post(run_url(uuid.uuid4()))
    one = await client.post(slot_url(uuid.uuid4(), 1))

    for response in (whole, one):
        assert response.status_code == 404
        assert response.json()["code"] == "SIMULATION_NOT_FOUND"


@pytest.mark.parametrize("slot_no", [0, 3, 9])
async def test_a_slot_the_run_does_not_have_is_404(
    client: AsyncClient, running: Running, slot_no: int
) -> None:
    response = await client.post(slot_url(running.simulation_id, slot_no))

    assert response.status_code == 404
    assert response.json()["code"] == "SLOT_NOT_FOUND"
    await client.post(run_url(running.simulation_id))
    await running.manager.wait_idle()


async def test_cancelling_requires_login(client: AsyncClient) -> None:
    for url in (run_url(uuid.uuid4()), slot_url(uuid.uuid4(), 1)):
        response = await client.post(url)

        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"

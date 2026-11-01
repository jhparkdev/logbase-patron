"""시뮬레이터 API 테스트들이 함께 쓰는 도구."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.simulation_manager import SimulationManager
from app.services.simulation_ports import SimulationDeps, SimulationJob
from app.services.simulation_recorders import ScopedRequestRecorder
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_scoped_store import ScopedSimulationStore
from tests.db_helpers import T0
from tests.services.simulation_fakes import FakeImageSource

CREATE = "/api/simulations"


class FakeManager:
    """작업을 실제로 돌리지 않고 어떤 작업이 언제 넘어왔는지만 기록한다."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.jobs: list[SimulationJob] = []
        self.registry = CancelRegistry()

    def start(self, job: SimulationJob) -> None:
        self.events.append("start")
        self.jobs.append(job)


class SerializedSessions:
    """세션을 한 번에 하나만 열게 하는 sessionmaker 대역.

    테스트는 연결 하나를 모든 세션이 나눠 쓴다. 운영처럼 연결을 따로 쓰면 필요 없는 장치이고,
    모델 호출은 그대로 동시에 돈다. DB 에 쓰는 구간만 차례로 지나간다.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        async with self._lock, self._sessions.begin() as session:
            yield session


def create_body(model_ids: list[int], **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "test_type": "CUSTOM",
        "prompt_text": "요약해 주세요",
        "models": [
            {"model_id": model_ids[0], "execution_provider": "DeepInfra"},
            {"model_id": model_ids[1], "execution_provider": "DekaLLM"},
        ],
    }
    body.update(overrides)
    return body


async def count(session: AsyncSession, table: Any) -> int:
    return await session.scalar(select(func.count()).select_from(table)) or 0


def build_sessions(db_session: AsyncSession) -> SerializedSessions:
    """테스트 연결 위에서 세션을 여는 sessionmaker 대역."""
    return SerializedSessions(
        async_sessionmaker(
            bind=db_session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
    )


def build_manager(
    db_session: AsyncSession,
    caller: Any,
    *,
    registry: CancelRegistry | None = None,
    sessions: SerializedSessions | None = None,
    now: datetime = T0 + timedelta(seconds=5),
) -> SimulationManager:
    """테스트 연결 위에서 실제로 DB 에 쓰는 작업 관리자. 모델 호출만 가짜다."""
    sessions = sessions or build_sessions(db_session)
    return SimulationManager(
        SimulationDeps(
            caller=caller,
            recorder=ScopedRequestRecorder(sessions),  # type: ignore[arg-type]
            store=ScopedSimulationStore(sessions),  # type: ignore[arg-type]
            now=lambda: now,
            images=FakeImageSource(),
        ),
        registry=registry,
    )

"""SimulationStore 포트의 백그라운드용 구현. 쓸 때마다 새 세션을 열고 commit 한다.

이유는 simulation_recorders 와 같다. 접수는 요청 세션으로 DbSimulationStore 를 직접 쓰고,
요청이 끝난 뒤 도는 실행과 취소는 이 클래스를 쓴다.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_ports import NewResult, NewRun, SlotRecord, SlotState
from app.services.simulation_store import DbSimulationStore


class ScopedSimulationStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def insert_run(self, run: NewRun) -> None:
        async with self._sessions.begin() as session:
            await DbSimulationStore(session).insert_run(run)

    async def insert_result(self, result: NewResult) -> None:
        async with self._sessions.begin() as session:
            await DbSimulationStore(session).insert_result(result)

    async def mark_started(self, simulation_id: uuid.UUID, now: datetime) -> None:
        async with self._sessions.begin() as session:
            await DbSimulationStore(session).mark_started(simulation_id, now)

    async def touch_heartbeat(self, simulation_id: uuid.UUID, now: datetime) -> None:
        async with self._sessions.begin() as session:
            await DbSimulationStore(session).touch_heartbeat(simulation_id, now)

    async def save_validation(self, request_id: uuid.UUID, record: SlotRecord) -> None:
        async with self._sessions.begin() as session:
            await DbSimulationStore(session).save_validation(request_id, record)

    async def list_slots(self, simulation_id: uuid.UUID) -> list[SlotState] | None:
        async with self._sessions.begin() as session:
            return await DbSimulationStore(session).list_slots(simulation_id)

    async def final_statuses(self, simulation_id: uuid.UUID) -> list[RequestStatus]:
        async with self._sessions.begin() as session:
            return await DbSimulationStore(session).final_statuses(simulation_id)

    async def mark_finished(
        self, simulation_id: uuid.UUID, status: SimulationStatus, now: datetime
    ) -> None:
        async with self._sessions.begin() as session:
            await DbSimulationStore(session).mark_finished(simulation_id, status, now)

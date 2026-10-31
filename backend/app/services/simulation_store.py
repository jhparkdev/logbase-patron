"""simulation_runs·simulation_results 저장(SimulationStore 의 DB 구현).

넘겨받은 세션 안에서만 일하고 commit 하지 않는다. 트랜잭션은 부르는 쪽이 정한다.
접수는 요청 세션 하나로 실행·호출 이력·칸 결과를 함께 묶고, 백그라운드 실행은 저장마다 새 세션을 연다.
호출 이력(ai_requests)은 상태를 읽기만 한다. 쓰기는 services/requests.py 몫이다.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    RequestStatus,
    SimulationResult,
    SimulationRun,
    SimulationStatus,
)
from app.services.simulation_ports import NewResult, NewRun, SlotRecord, SlotState

# 종료되지 않은 실행만 상태를 바꾼다. 종료된 실행의 상태와 시각은 다시 쓰지 않는다
_OPEN_RUN = (SimulationStatus.PENDING, SimulationStatus.RUNNING)


class DbSimulationStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_run(self, run: NewRun) -> None:
        self._session.add(
            SimulationRun(
                simulation_id=run.simulation_id,
                rerun_of_simulation_id=run.rerun_of_simulation_id,
                test_type=run.test_type,
                scenario_id=run.scenario_id,
                prompt_text=run.prompt_text,
                input_text=run.input_text,
                json_schema=run.json_schema,
                execution_config=run.execution_config,
                routing_policy=run.routing_policy,
                input_hash=run.input_hash,
                model_count=run.model_count,
                status=SimulationStatus.PENDING,
                project_id=run.project_id,
                key_id=run.key_id,
                executed_by=run.executed_by,
                requested_at=run.requested_at,
                data_source=run.data_source,
            )
        )
        # 뒤따르는 호출 이력·칸 결과가 이 행을 외래키로 가리키므로 바로 보낸다
        await self._session.flush()

    async def insert_result(self, result: NewResult) -> None:
        self._session.add(
            SimulationResult(
                simulation_id=result.simulation_id,
                request_id=result.request_id,
                slot_no=result.slot_no,
                model_id=result.model_id,
                execution_provider=result.execution_provider,
                model_status_at_run=result.model_status_at_run,
                model_display_name_at_run=result.model_display_name_at_run,
            )
        )
        await self._session.flush()

    async def mark_started(self, simulation_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(SimulationRun)
            .where(
                SimulationRun.simulation_id == simulation_id,
                SimulationRun.status == SimulationStatus.PENDING,
            )
            .values(status=SimulationStatus.RUNNING, started_at=now, heartbeat_at=now)
        )

    async def touch_heartbeat(self, simulation_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(SimulationRun)
            .where(
                SimulationRun.simulation_id == simulation_id,
                SimulationRun.status == SimulationStatus.RUNNING,
            )
            .values(heartbeat_at=now)
        )

    async def save_validation(self, request_id: uuid.UUID, record: SlotRecord) -> None:
        await self._session.execute(
            update(SimulationResult)
            .where(SimulationResult.request_id == request_id)
            .values(
                json_parse_status=record.json_parse_status,
                schema_validation_status=record.schema_validation_status,
                missing_required_fields=record.missing_required_fields,
                validation_errors=record.validation_errors,
            )
        )

    async def list_slots(self, simulation_id: uuid.UUID) -> list[SlotState] | None:
        exists = await self._session.scalar(
            select(SimulationRun.simulation_id).where(
                SimulationRun.simulation_id == simulation_id
            )
        )
        if exists is None:
            return None
        rows = await self._session.execute(
            select(
                SimulationResult.request_id, SimulationResult.slot_no, AIRequest.status
            )
            .join(AIRequest, AIRequest.request_id == SimulationResult.request_id)
            .where(
                SimulationResult.simulation_id == simulation_id,
                SimulationResult.is_final_attempt,
            )
            .order_by(SimulationResult.slot_no)
        )
        return [
            SlotState(
                request_id=row.request_id,
                slot_no=row.slot_no,
                status=RequestStatus(row.status),
            )
            for row in rows
        ]

    async def final_statuses(self, simulation_id: uuid.UUID) -> list[RequestStatus]:
        return [slot.status for slot in await self.list_slots(simulation_id) or []]

    async def mark_finished(
        self, simulation_id: uuid.UUID, status: SimulationStatus, now: datetime
    ) -> None:
        await self._session.execute(
            update(SimulationRun)
            .where(
                SimulationRun.simulation_id == simulation_id,
                SimulationRun.status.in_(_OPEN_RUN),
            )
            .values(status=status, completed_at=now)
        )

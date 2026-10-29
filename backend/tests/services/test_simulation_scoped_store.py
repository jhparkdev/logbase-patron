import uuid
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import SimulationRun, SimulationStatus
from app.services.simulation_scoped_store import ScopedSimulationStore
from app.services.simulation_store import DbSimulationStore
from tests.db_helpers import T0, Factory
from tests.services.test_simulation_recorders import CountingSessions
from tests.services.test_simulation_store import add_slot, new_run

S = SimulationStatus
LATER = T0 + timedelta(seconds=30)


@pytest.fixture
def sessions(db_session: AsyncSession) -> CountingSessions:
    return CountingSessions(
        async_sessionmaker(
            bind=db_session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
    )


async def saved_status(session: AsyncSession, simulation_id: uuid.UUID) -> str:
    run = await session.get(SimulationRun, simulation_id)
    assert run is not None
    await session.refresh(run)
    return run.status


async def test_scoped_store_writes_the_run_lifecycle_through_new_sessions(
    factory: Factory, db_session: AsyncSession, sessions: CountingSessions
) -> None:
    run = await new_run(factory)
    # 접수는 요청 세션이 한다. 백그라운드는 그 뒤부터 맡는다
    await DbSimulationStore(db_session).insert_run(run)
    store = ScopedSimulationStore(sessions)  # type: ignore[arg-type]

    await store.mark_started(run.simulation_id, T0)
    await store.touch_heartbeat(run.simulation_id, LATER)
    await store.mark_finished(run.simulation_id, S.SUCCESS, LATER)

    assert sessions.opened == 3
    assert await saved_status(db_session, run.simulation_id) == S.SUCCESS


async def test_scoped_store_reads_the_slots_of_a_run(
    factory: Factory, db_session: AsyncSession, sessions: CountingSessions
) -> None:
    run = await new_run(factory)
    local = DbSimulationStore(db_session)
    await local.insert_run(run)
    request_id = await add_slot(factory, local, run, slot_no=1)
    store = ScopedSimulationStore(sessions)  # type: ignore[arg-type]

    slots = await store.list_slots(run.simulation_id)
    statuses = await store.final_statuses(run.simulation_id)

    assert slots is not None
    assert [(s.request_id, s.slot_no) for s in slots] == [(request_id, 1)]
    assert len(statuses) == 1
    assert await store.list_slots(uuid.uuid4()) is None

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DataSource,
    ModelStatus,
    RequestStatus,
    SimulationResult,
    SimulationRun,
    SimulationStatus,
    ValidationStatus,
)
from app.models import TestType as RunType
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_ports import NewResult, NewRun, SlotState
from app.services.simulation_store import DbSimulationStore
from tests.db_helpers import T0, Factory
from tests.services.simulation_fakes import failed, ok

R = RequestStatus
S = SimulationStatus
SCHEMA = {"type": "object", "required": ["title"]}
LATER = T0 + timedelta(seconds=30)


@pytest.fixture
def store(db_session: AsyncSession) -> DbSimulationStore:
    return DbSimulationStore(db_session)


async def new_run(factory: Factory, **overrides: object) -> NewRun:
    project = await factory.project()
    key = await factory.api_key(project_id=project["project_id"])
    user = await factory.user()
    values: dict[str, object] = {
        "simulation_id": uuid.uuid4(),
        "rerun_of_simulation_id": None,
        "test_type": RunType.CUSTOM,
        "scenario_id": None,
        "prompt_text": "요약해 주세요",
        "input_text": "본문",
        "json_schema": SCHEMA,
        "execution_config": {"max_tokens": 4096},
        "routing_policy": {"allow_fallbacks": False, "require_parameters": True},
        "input_hash": "a" * 64,
        "model_count": 2,
        "project_id": project["project_id"],
        "key_id": key["key_id"],
        "executed_by": user["user_id"],
        "requested_at": T0,
        "data_source": DataSource.LIVE,
    }
    values.update(overrides)
    return NewRun(**values)  # type: ignore[arg-type]


async def add_slot(
    factory: Factory,
    store: DbSimulationStore,
    run: NewRun,
    slot_no: int,
    status: RequestStatus = R.PENDING,
) -> uuid.UUID:
    """칸 하나: 호출 이력(건호님 몫이라 테스트에서는 직접 넣는다)과 칸 결과."""
    model = await factory.model(status="ACTIVE")
    request = await factory.ai_request(
        usage_origin="SIMULATION",
        simulation_id=run.simulation_id,
        project_id=run.project_id,
        key_id=run.key_id,
        executed_by=run.executed_by,
        status=status.value,
        **_terminal_values(status),
    )
    await store.insert_result(
        NewResult(
            simulation_id=run.simulation_id,
            request_id=request["request_id"],
            slot_no=slot_no,
            model_id=model["model_id"],
            execution_provider="DeepInfra",
            model_status_at_run=ModelStatus.ACTIVE,
            model_display_name_at_run=f"모델 {slot_no}",
        )
    )
    return request["request_id"]


def _terminal_values(status: RequestStatus) -> dict[str, object]:
    # DB 제약: 실패·시간 초과에는 오류 유형이 있어야 한다
    if status in (R.FAILED, R.TIMEOUT):
        return {"error_type": "UNKNOWN_ERROR"}
    return {}


async def saved_run(session: AsyncSession, simulation_id: uuid.UUID) -> SimulationRun:
    run = await session.get(SimulationRun, simulation_id)
    assert run is not None
    await session.refresh(run)
    return run


# --- 접수 때 저장 ---


async def test_run_is_saved_as_pending_with_the_confirmed_inputs(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)

    await store.insert_run(run)

    saved = await saved_run(db_session, run.simulation_id)
    assert saved.status == S.PENDING
    assert (saved.prompt_text, saved.input_text) == ("요약해 주세요", "본문")
    assert saved.json_schema == SCHEMA
    assert saved.execution_config == {"max_tokens": 4096}
    assert saved.routing_policy == {
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert (saved.model_count, saved.data_source) == (2, DataSource.LIVE)
    assert saved.requested_at == T0
    assert saved.started_at is None and saved.completed_at is None


async def test_result_row_keeps_the_model_snapshot_and_starts_unchecked(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)

    request_id = await add_slot(factory, store, run, slot_no=1)

    row = await db_session.scalar(
        select(SimulationResult).where(SimulationResult.request_id == request_id)
    )
    assert row is not None
    assert (row.slot_no, row.execution_provider) == (1, "DeepInfra")
    assert (row.model_status_at_run, row.model_display_name_at_run) == (
        ModelStatus.ACTIVE,
        "모델 1",
    )
    assert row.is_final_attempt is True
    # 검증은 응답을 받은 뒤에 채운다
    assert row.json_parse_status is None and row.schema_validation_status is None


# --- 실행 중 ---


async def test_start_marks_the_run_running_once(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)

    await store.mark_started(run.simulation_id, T0)
    await store.mark_started(run.simulation_id, LATER)

    saved = await saved_run(db_session, run.simulation_id)
    assert saved.status == S.RUNNING
    assert (saved.started_at, saved.heartbeat_at) == (T0, T0)


async def test_heartbeat_is_recorded_only_while_running(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)
    await store.mark_started(run.simulation_id, T0)

    await store.touch_heartbeat(run.simulation_id, LATER)
    assert (await saved_run(db_session, run.simulation_id)).heartbeat_at == LATER

    await store.mark_finished(run.simulation_id, S.SUCCESS, LATER)
    await store.touch_heartbeat(run.simulation_id, LATER + timedelta(seconds=30))
    assert (await saved_run(db_session, run.simulation_id)).heartbeat_at == LATER


async def test_validation_result_is_saved_on_the_slot(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)
    request_id = await add_slot(factory, store, run, slot_no=1)

    await store.save_validation(request_id, to_slot_record(ok("{}"), SCHEMA))

    row = await db_session.scalar(
        select(SimulationResult).where(SimulationResult.request_id == request_id)
    )
    assert row is not None
    await db_session.refresh(row)
    assert (row.json_parse_status, row.schema_validation_status) == (
        ValidationStatus.PASSED,
        ValidationStatus.FAILED,
    )
    assert row.missing_required_fields == ["title"]
    assert row.validation_errors is not None
    assert row.validation_errors["truncated"] is False


async def test_a_slot_without_a_response_is_saved_as_not_executed(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)
    request_id = await add_slot(factory, store, run, slot_no=1)

    await store.save_validation(request_id, to_slot_record(failed(), SCHEMA))

    row = await db_session.scalar(
        select(SimulationResult).where(SimulationResult.request_id == request_id)
    )
    assert row is not None
    await db_session.refresh(row)
    assert row.json_parse_status == ValidationStatus.NOT_EXECUTED
    assert row.missing_required_fields is None and row.validation_errors is None


# --- 칸 상태 읽기 (취소·전체 상태 계산이 쓴다) ---


async def test_slots_are_read_in_slot_order_with_the_call_status(
    factory: Factory, store: DbSimulationStore
) -> None:
    run = await new_run(factory, model_count=3)
    await store.insert_run(run)
    third = await add_slot(factory, store, run, slot_no=3, status=R.RUNNING)
    first = await add_slot(factory, store, run, slot_no=1, status=R.SUCCESS)
    second = await add_slot(factory, store, run, slot_no=2, status=R.FAILED)

    slots = await store.list_slots(run.simulation_id)

    assert slots == [
        SlotState(request_id=first, slot_no=1, status=R.SUCCESS),
        SlotState(request_id=second, slot_no=2, status=R.FAILED),
        SlotState(request_id=third, slot_no=3, status=R.RUNNING),
    ]
    assert await store.final_statuses(run.simulation_id) == [
        R.SUCCESS,
        R.FAILED,
        R.RUNNING,
    ]


async def test_only_the_final_attempt_of_a_slot_is_read(
    factory: Factory,
    store: DbSimulationStore,
    db_session: AsyncSession,
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)
    earlier = await add_slot(factory, store, run, slot_no=1, status=R.FAILED)
    row = await db_session.scalar(
        select(SimulationResult).where(SimulationResult.request_id == earlier)
    )
    assert row is not None
    row.is_final_attempt = False
    await db_session.flush()
    final = await add_slot(factory, store, run, slot_no=1, status=R.SUCCESS)

    slots = await store.list_slots(run.simulation_id)

    assert slots == [SlotState(request_id=final, slot_no=1, status=R.SUCCESS)]


async def test_unknown_simulation_has_no_slots(store: DbSimulationStore) -> None:
    assert await store.list_slots(uuid.uuid4()) is None


async def test_a_run_without_slots_is_an_empty_list(
    factory: Factory, store: DbSimulationStore
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)

    assert await store.list_slots(run.simulation_id) == []


# --- 종료 ---


async def test_finish_records_the_overall_status_and_time(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    run = await new_run(factory)
    await store.insert_run(run)
    await store.mark_started(run.simulation_id, T0)

    await store.mark_finished(run.simulation_id, S.PARTIAL_SUCCESS, LATER)

    saved = await saved_run(db_session, run.simulation_id)
    assert (saved.status, saved.completed_at) == (S.PARTIAL_SUCCESS, LATER)


async def test_a_finished_run_is_never_rewritten(
    factory: Factory, store: DbSimulationStore, db_session: AsyncSession
) -> None:
    # 종료된 실행의 상태와 시각은 바꾸지 않는다(이력 덮어쓰기 금지)
    run = await new_run(factory)
    await store.insert_run(run)
    await store.mark_finished(run.simulation_id, S.SUCCESS, LATER)

    await store.mark_finished(run.simulation_id, S.CANCELLED, LATER + timedelta(1))
    await store.mark_started(run.simulation_id, LATER + timedelta(2))

    saved = await saved_run(db_session, run.simulation_id)
    assert (saved.status, saved.completed_at, saved.started_at) == (
        S.SUCCESS,
        LATER,
        None,
    )

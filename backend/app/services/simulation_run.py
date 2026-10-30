import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import datetime

from app.models import SimulationStatus
from app.openrouter.errors import ErrorType as CallErrorType
from app.openrouter.failures import build_failure_result
from app.openrouter.result import CallResult, CallStatus
from app.services.simulation_input import (
    HEARTBEAT_INTERVAL_SECONDS,
    SIMULATION_TIMEOUT_SECONDS,
)
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_ports import (
    SimulationDeps,
    SimulationJob,
    SimulationStore,
    SlotPlan,
)
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_status import compute_overall_status, is_run_finished

# 로그에는 request_id 와 상태, 예외 종류만 남긴다. 프롬프트·응답·예외 메시지(키가 들어갈 수 있음)는 남기지 않는다
logger = logging.getLogger(__name__)


async def run_simulation(
    job: SimulationJob,
    deps: SimulationDeps,
    *,
    cancel_events: Mapping[uuid.UUID, asyncio.Event] | None = None,
    timeout_seconds: float = SIMULATION_TIMEOUT_SECONDS,
    heartbeat_interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
) -> SimulationStatus:
    """저장이 끝난 비교 한 건을 실행한다. 모델마다 병렬로 호출하고, 한 칸의 실패가 다른 칸에 번지지 않는다.

    cancel_events 는 호출 ID 별 취소 신호다. 신호가 켜지면 그 칸의 호출이 CANCELLED 로 끝난다.
    모든 칸이 끝나면 전체 상태를 계산해 기록한다. 칸 하나라도 기록하지 못해 끝나지 않았다면
    실행을 끝난 것으로 표시하지 않고 복구 작업에 맡긴다.
    """
    events = cancel_events or {}
    await deps.store.mark_started(job.simulation_id, deps.now())
    heartbeat = asyncio.create_task(
        _beat(deps.store, job.simulation_id, deps.now, heartbeat_interval_seconds)
    )
    slot_runs = [
        _run_slot(slot, job, deps, _cancel_signal(events, slot), timeout_seconds)
        for slot in job.slots
    ]
    try:
        # return_exceptions: 한 칸에서 예외가 나도 나머지 칸은 끝까지 돌린다
        outcomes = await asyncio.gather(*slot_runs, return_exceptions=True)
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat
    _log_unrecorded_slots(job, outcomes)

    overall = compute_overall_status(await deps.store.final_statuses(job.simulation_id))
    if not is_run_finished(overall):
        logger.warning(
            "simulation left for recovery: simulation_id=%s", job.simulation_id
        )
        return overall
    await deps.store.mark_finished(job.simulation_id, overall, deps.now())
    return overall


async def run_registered_simulation(
    job: SimulationJob,
    deps: SimulationDeps,
    registry: CancelRegistry,
    *,
    timeout_seconds: float = SIMULATION_TIMEOUT_SECONDS,
    heartbeat_interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
) -> SimulationStatus:
    """취소 신호 보관함에 등록한 채로 실행한다. 끝나면(실패해도) 신호를 버린다."""
    events = registry.register(
        job.simulation_id, [slot.request_id for slot in job.slots]
    )
    try:
        return await run_simulation(
            job,
            deps,
            cancel_events=events,
            timeout_seconds=timeout_seconds,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
    finally:
        registry.release(job.simulation_id)


def _cancel_signal(
    events: Mapping[uuid.UUID, asyncio.Event], slot: SlotPlan
) -> asyncio.Event:
    # 보관함 없이 돌릴 때는 아무도 켜지 않는 신호를 준다
    return events.get(slot.request_id) or asyncio.Event()


def _log_unrecorded_slots(
    job: SimulationJob, outcomes: list[None | BaseException]
) -> None:
    for slot, outcome in zip(job.slots, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.error(
                "slot not recorded: request_id=%s error=%s",
                slot.request_id,
                type(outcome).__name__,
            )


async def _run_slot(
    slot: SlotPlan,
    job: SimulationJob,
    deps: SimulationDeps,
    cancel: asyncio.Event,
    timeout_seconds: float,
) -> None:
    started_at = deps.now()
    if not await deps.recorder.mark_running(slot.request_id, started_at):
        return  # 시작 전에 이미 취소되었다
    try:
        result = await deps.caller(
            request_id=slot.request_id,
            model_id=slot.openrouter_model_id,
            messages=job.messages,
            max_tokens=job.max_tokens,
            timeout_seconds=timeout_seconds,
            json_schema=job.json_schema,
            provider_order=[slot.execution_provider],
            allow_fallbacks=job.allow_fallbacks,
            cancel=cancel,
        )
    except Exception as error:  # noqa: BLE001 - 예상 밖 오류는 이 칸의 실패로 바꿔 기록한다
        logger.error(
            "model call raised: request_id=%s error=%s",
            slot.request_id,
            type(error).__name__,
        )
        result = _unexpected_failure(slot, started_at, deps.now())
    record = to_slot_record(result, job.json_schema)
    if not await deps.recorder.record_finished(slot.request_id, record, deps.now()):
        # 이미 취소로 끝난 칸이다. 종료된 호출의 상태는 바꾸지 않으므로 늦게 온 결과는 저장하지 않는다
        return
    await deps.recorder.save_payload(
        slot.request_id, job.messages, record.response_text
    )
    await deps.store.save_validation(slot.request_id, record)


def _unexpected_failure(
    slot: SlotPlan, started_at: datetime, finished_at: datetime
) -> CallResult:
    # 예외 원문은 키나 내부 정보가 들어 있을 수 있어 옮기지 않고 정해진 문구만 쓴다
    return build_failure_result(
        status=CallStatus.FAILED,
        error_type=CallErrorType.UNKNOWN_ERROR,
        requested_model=slot.openrouter_model_id,
        started_at=started_at,
        finished_at=finished_at,
    )


async def _beat(
    store: SimulationStore,
    simulation_id: uuid.UUID,
    now: Callable[[], datetime],
    interval_seconds: float,
) -> None:
    """실행 중임을 주기적으로 기록한다. 기록 실패가 실행을 멈추지 않게 한다."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await store.touch_heartbeat(simulation_id, now())
        except Exception as error:  # noqa: BLE001 - 하트비트 기록 실패로 실행을 멈추지 않는다
            logger.warning(
                "heartbeat failed: simulation_id=%s error=%s",
                simulation_id,
                type(error).__name__,
            )

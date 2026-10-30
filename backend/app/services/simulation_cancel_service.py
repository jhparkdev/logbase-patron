import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_cancel import CancelDecision, decide_request_cancel
from app.services.simulation_ports import RequestRecorder, SimulationStore, SlotState
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_status import compute_overall_status, is_run_finished


class SimulationNotFoundError(LookupError):
    """없는 실행이다."""


class SlotNotFoundError(LookupError):
    """그 실행에 없는 칸 번호다."""


@dataclass(frozen=True)
class CancelDeps:
    store: SimulationStore
    recorder: RequestRecorder
    registry: CancelRegistry
    now: Callable[[], datetime]


@dataclass(frozen=True)
class SlotCancelOutcome:
    """칸 하나의 취소 처리 결과. 응답 스키마(RequestCancelOutcome)와 같은 칸이다."""

    request_id: uuid.UUID
    slot_no: int
    decision: CancelDecision
    status: RequestStatus  # 처리 뒤 이 칸의 상태


@dataclass(frozen=True)
class CancelReport:
    simulation_id: uuid.UUID
    status: SimulationStatus  # 처리 뒤 실행 전체 상태
    outcomes: list[SlotCancelOutcome]


async def cancel_slot(
    simulation_id: uuid.UUID, slot_no: int, deps: CancelDeps
) -> CancelReport:
    """모델 한 칸을 취소한다."""
    return await _cancel(simulation_id, deps, only_slot=slot_no)


async def cancel_simulation(simulation_id: uuid.UUID, deps: CancelDeps) -> CancelReport:
    """실행 전체를 취소한다. 이미 끝난 칸은 그대로 두고 진행 중인 칸만 취소한다."""
    return await _cancel(simulation_id, deps, only_slot=None)


async def _cancel(
    simulation_id: uuid.UUID, deps: CancelDeps, only_slot: int | None
) -> CancelReport:
    slots = await deps.store.list_slots(simulation_id)
    if slots is None:
        raise SimulationNotFoundError
    targets = [s for s in slots if only_slot is None or s.slot_no == only_slot]
    if not targets:
        raise SlotNotFoundError

    outcomes = [await _cancel_one(simulation_id, slot, deps) for slot in targets]

    after = await deps.store.list_slots(simulation_id) or []
    overall = compute_overall_status([slot.status for slot in after])
    if _cancel_must_finish_run(
        outcomes, overall, task_running=deps.registry.is_active(simulation_id)
    ):
        await deps.store.mark_finished(simulation_id, overall, deps.now())
    return CancelReport(simulation_id=simulation_id, status=overall, outcomes=outcomes)


def _cancel_must_finish_run(
    outcomes: list[SlotCancelOutcome], overall: SimulationStatus, *, task_running: bool
) -> bool:
    """이번 취소가 실행 종료까지 기록해야 하는가.

    실행을 끝난 것으로 기록하는 일은 보통 돌고 있는 실행 작업이 한다(마지막 호출이 취소로 끝난 뒤).
    그 작업이 없는데 이번 취소로 모든 칸이 끝났다면 여기서 기록한다. 이미 끝난 실행은 다시 쓰지 않는다.
    """
    changed_something = any(o.decision == CancelDecision.CANCEL for o in outcomes)
    return changed_something and is_run_finished(overall) and not task_running


async def _cancel_one(
    simulation_id: uuid.UUID, slot: SlotState, deps: CancelDeps
) -> SlotCancelOutcome:
    decision = decide_request_cancel(slot.status)
    if decision != CancelDecision.CANCEL:
        return _outcome(slot, decision, slot.status)
    if await deps.recorder.cancel_if_open(slot.request_id, deps.now()):
        deps.registry.signal(slot.request_id)  # 진행 중인 호출이 있으면 멈추게 한다
        return _outcome(slot, decision, RequestStatus.CANCELLED)
    # 목록을 읽은 뒤 취소하기 전에 다른 쪽이 먼저 끝냈다. 현재 상태를 다시 읽어 그대로 알린다
    current = await _current_status(simulation_id, slot, deps)
    return _outcome(slot, decide_request_cancel(current), current)


def _outcome(
    slot: SlotState, decision: CancelDecision, status: RequestStatus
) -> SlotCancelOutcome:
    return SlotCancelOutcome(
        request_id=slot.request_id,
        slot_no=slot.slot_no,
        decision=decision,
        status=status,
    )


async def _current_status(
    simulation_id: uuid.UUID, slot: SlotState, deps: CancelDeps
) -> RequestStatus:
    for fresh in await deps.store.list_slots(simulation_id) or []:
        if fresh.request_id == slot.request_id:
            return fresh.status
    return slot.status

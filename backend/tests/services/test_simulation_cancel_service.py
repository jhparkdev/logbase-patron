import asyncio
import uuid

import pytest

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_cancel import CancelDecision
from app.services.simulation_cancel_service import (
    CancelDeps,
    SimulationNotFoundError,
    SlotNotFoundError,
    cancel_simulation,
    cancel_slot,
)
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_run import run_registered_simulation
from tests.services.simulation_fakes import NOW, Harness, until_cancelled

R = RequestStatus
S = SimulationStatus
D = CancelDecision


class CancelHarness(Harness):
    """실행이 저장된 상태에서 취소만 시험한다. 호출 이력의 현재 상태를 칸마다 정해 둔다."""

    def __init__(self, statuses: list[RequestStatus]) -> None:
        super().__init__(count=len(statuses))
        for slot, status in zip(self.slots, statuses, strict=True):
            self.recorder.statuses[slot.request_id] = status
        self.registry = CancelRegistry()
        self.events = self.registry.register(
            self.job.simulation_id, [slot.request_id for slot in self.slots]
        )
        self.cancel_deps = CancelDeps(
            store=self.store,
            recorder=self.recorder,
            registry=self.registry,
            now=lambda: NOW,
        )

    def outcome_of(self, report, slot_no: int):
        return next(o for o in report.outcomes if o.slot_no == slot_no)


# --- 모델 하나 취소 ---


async def test_cancelling_a_running_slot_stops_its_call() -> None:
    h = CancelHarness([R.RUNNING, R.RUNNING])

    report = await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)

    outcome = h.outcome_of(report, 1)
    assert (outcome.decision, outcome.status) == (D.CANCEL, R.CANCELLED)
    assert outcome.request_id == h.request_id(1)
    assert h.recorder.statuses[h.request_id(1)] == R.CANCELLED
    assert h.events[h.request_id(1)].is_set()  # 진행 중인 호출에 멈추라고 알린다
    assert not h.events[h.request_id(2)].is_set()


async def test_only_the_chosen_slot_is_in_the_report() -> None:
    h = CancelHarness([R.RUNNING, R.RUNNING, R.RUNNING])

    report = await cancel_slot(h.job.simulation_id, 2, h.cancel_deps)

    assert [o.slot_no for o in report.outcomes] == [2]
    assert report.simulation_id == h.job.simulation_id
    assert report.status == S.RUNNING  # 나머지가 진행 중이다


async def test_cancelling_a_pending_slot_works_before_it_starts() -> None:
    h = CancelHarness([R.PENDING, R.PENDING])

    report = await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)

    assert h.outcome_of(report, 1).status == R.CANCELLED
    assert h.recorder.statuses[h.request_id(2)] == R.PENDING


async def test_cancelling_twice_gives_the_same_result() -> None:
    # C-08: 같은 취소를 두 번 눌러도 결과가 같다
    h = CancelHarness([R.RUNNING, R.RUNNING])
    await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)
    h.events[h.request_id(1)].clear()

    report = await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)

    outcome = h.outcome_of(report, 1)
    assert (outcome.decision, outcome.status) == (D.ALREADY_CANCELLED, R.CANCELLED)
    assert not h.events[h.request_id(1)].is_set()  # 두 번째는 아무것도 하지 않는다


@pytest.mark.parametrize("status", [R.SUCCESS, R.FAILED, R.TIMEOUT])
async def test_cancelling_a_finished_slot_changes_nothing(status: R) -> None:
    # C-09: 이미 끝난 결과와 비용은 건드리지 않는다
    h = CancelHarness([status, R.RUNNING])

    report = await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)

    outcome = h.outcome_of(report, 1)
    assert (outcome.decision, outcome.status) == (D.ALREADY_TERMINAL, status)
    assert h.recorder.statuses[h.request_id(1)] == status
    assert not h.events[h.request_id(1)].is_set()


async def test_a_call_that_finishes_just_before_the_cancel_wins() -> None:
    # 목록을 읽은 뒤 취소하기 직전에 정상 완료가 먼저 도착했다. 완료된 결과를 지킨다
    h = CancelHarness([R.RUNNING])

    async def finished_first(request_id: uuid.UUID, now: object) -> bool:
        h.recorder.statuses[request_id] = R.SUCCESS
        return False

    h.recorder.cancel_if_open = finished_first  # type: ignore[method-assign]

    report = await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)

    outcome = h.outcome_of(report, 1)
    assert (outcome.decision, outcome.status) == (D.ALREADY_TERMINAL, R.SUCCESS)
    assert not h.events[h.request_id(1)].is_set()


async def test_unknown_slot_number_is_an_error() -> None:
    h = CancelHarness([R.RUNNING, R.RUNNING])

    with pytest.raises(SlotNotFoundError):
        await cancel_slot(h.job.simulation_id, 4, h.cancel_deps)


async def test_unknown_simulation_is_an_error() -> None:
    h = CancelHarness([R.RUNNING])

    with pytest.raises(SimulationNotFoundError):
        await cancel_slot(uuid.UUID(int=12345), 1, h.cancel_deps)
    with pytest.raises(SimulationNotFoundError):
        await cancel_simulation(uuid.UUID(int=12345), h.cancel_deps)


# --- 실행 전체 취소 ---


async def test_cancelling_the_whole_run_cancels_every_open_slot() -> None:
    h = CancelHarness([R.SUCCESS, R.RUNNING, R.PENDING])

    report = await cancel_simulation(h.job.simulation_id, h.cancel_deps)

    assert [(o.slot_no, o.decision, o.status) for o in report.outcomes] == [
        (1, D.ALREADY_TERMINAL, R.SUCCESS),
        (2, D.CANCEL, R.CANCELLED),
        (3, D.CANCEL, R.CANCELLED),
    ]
    assert report.status == S.PARTIAL_SUCCESS  # 성공한 결과가 남았다
    assert h.events[h.request_id(2)].is_set()


async def test_cancelling_everything_ends_the_run_as_cancelled() -> None:
    h = CancelHarness([R.RUNNING, R.PENDING])

    report = await cancel_simulation(h.job.simulation_id, h.cancel_deps)

    assert report.status == S.CANCELLED


async def test_cancelling_a_finished_run_is_not_an_error() -> None:
    h = CancelHarness([R.SUCCESS, R.FAILED])

    report = await cancel_simulation(h.job.simulation_id, h.cancel_deps)

    assert {o.decision for o in report.outcomes} == {D.ALREADY_TERMINAL}
    assert report.status == S.PARTIAL_SUCCESS


# --- 실행을 끝난 것으로 표시하는 책임 ---


async def test_the_running_task_finishes_the_run_not_the_cancel() -> None:
    # 실행 중인 작업이 있으면 마지막 호출이 취소 결과로 끝난 뒤 그 작업이 전체 상태를 기록한다
    h = CancelHarness([R.RUNNING])

    await cancel_simulation(h.job.simulation_id, h.cancel_deps)

    assert h.store.finished == []


async def test_cancel_finishes_the_run_when_no_task_is_running_it() -> None:
    # 서버가 다시 뜬 뒤처럼 실행 작업이 없는데 칸이 RUNNING 으로 남은 경우다
    h = CancelHarness([R.RUNNING, R.SUCCESS])
    h.registry.release(h.job.simulation_id)

    report = await cancel_simulation(h.job.simulation_id, h.cancel_deps)

    assert report.status == S.PARTIAL_SUCCESS
    assert h.store.finished == [(S.PARTIAL_SUCCESS, NOW)]


async def test_cancelling_a_finished_run_again_does_not_rewrite_it() -> None:
    # 종료된 실행의 상태와 시각은 다시 기록하지 않는다
    h = CancelHarness([R.SUCCESS, R.FAILED])
    h.registry.release(h.job.simulation_id)

    await cancel_simulation(h.job.simulation_id, h.cancel_deps)

    assert h.store.finished == []


async def test_cancel_does_not_finish_a_run_that_still_has_open_slots() -> None:
    h = CancelHarness([R.RUNNING, R.RUNNING])
    h.registry.release(h.job.simulation_id)

    await cancel_slot(h.job.simulation_id, 1, h.cancel_deps)

    assert h.store.finished == []


# --- 실제 실행과 함께 ---


async def test_cancelling_while_the_run_is_going_ends_with_partial_success() -> None:
    started = asyncio.Event()
    h = Harness(count=3)
    h.caller.behaviors = {h.model(2): until_cancelled(started)}
    registry = CancelRegistry()
    deps = CancelDeps(
        store=h.store, recorder=h.recorder, registry=registry, now=lambda: NOW
    )

    task = asyncio.create_task(run_registered_simulation(h.job, h.deps, registry))
    await asyncio.wait_for(started.wait(), timeout=1)
    report = await cancel_slot(h.job.simulation_id, 2, deps)
    status = await asyncio.wait_for(task, timeout=1)

    assert report.outcomes[0].status == R.CANCELLED
    assert status == S.PARTIAL_SUCCESS
    assert h.recorder.statuses[h.request_id(2)] == R.CANCELLED
    assert h.recorder.statuses[h.request_id(1)] == R.SUCCESS
    assert h.store.finished == [
        (S.PARTIAL_SUCCESS, NOW)
    ]  # 실행 작업이 한 번만 기록한다

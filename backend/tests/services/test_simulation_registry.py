import asyncio
import uuid
from typing import Any

import pytest

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_run import run_registered_simulation
from tests.services.simulation_fakes import Harness, until_cancelled

SIM = uuid.UUID(int=1)
REQ_A = uuid.UUID(int=2)
REQ_B = uuid.UUID(int=3)


def test_register_gives_one_event_per_call() -> None:
    registry = CancelRegistry()

    events = registry.register(SIM, [REQ_A, REQ_B])

    assert set(events) == {REQ_A, REQ_B}
    assert events[REQ_A] is not events[REQ_B]
    assert not events[REQ_A].is_set()


def test_signal_turns_on_only_that_calls_event() -> None:
    registry = CancelRegistry()
    events = registry.register(SIM, [REQ_A, REQ_B])

    registry.signal(REQ_A)

    assert events[REQ_A].is_set()
    assert not events[REQ_B].is_set()


def test_signal_for_an_unknown_call_does_nothing() -> None:
    # 이미 끝났거나 다른 서버가 실행 중인 호출이다. 오류가 아니다
    CancelRegistry().signal(REQ_A)


def test_simulation_is_active_until_released() -> None:
    registry = CancelRegistry()
    assert not registry.is_active(SIM)

    registry.register(SIM, [REQ_A])
    assert registry.is_active(SIM)

    registry.release(SIM)
    assert not registry.is_active(SIM)


def test_release_forgets_the_events_and_is_safe_to_repeat() -> None:
    registry = CancelRegistry()
    events = registry.register(SIM, [REQ_A])

    registry.release(SIM)
    registry.release(SIM)
    registry.signal(REQ_A)

    assert not events[REQ_A].is_set()


def test_other_simulations_are_not_affected_by_release() -> None:
    registry = CancelRegistry()
    other = uuid.UUID(int=50)
    registry.register(SIM, [REQ_A])
    registry.register(other, [REQ_B])

    registry.release(SIM)

    assert registry.is_active(other)


async def test_run_registered_wires_the_signals_and_releases_afterwards() -> None:
    started = asyncio.Event()
    h = Harness(count=2)
    h.caller.behaviors = {h.model(1): until_cancelled(started)}
    registry = CancelRegistry()

    task = asyncio.create_task(run_registered_simulation(h.job, h.deps, registry))
    await asyncio.wait_for(started.wait(), timeout=1)
    assert registry.is_active(h.job.simulation_id)
    registry.signal(h.request_id(1))

    status = await asyncio.wait_for(task, timeout=1)

    assert status == SimulationStatus.PARTIAL_SUCCESS
    assert h.recorder.statuses[h.request_id(1)] == RequestStatus.CANCELLED
    assert not registry.is_active(h.job.simulation_id)


async def test_run_registered_releases_even_when_the_run_fails() -> None:
    h = Harness(count=1)
    registry = CancelRegistry()

    async def broken_start(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("DB 오류")

    h.store.mark_started = broken_start  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await run_registered_simulation(h.job, h.deps, registry)

    assert not registry.is_active(h.job.simulation_id)

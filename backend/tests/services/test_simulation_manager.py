import asyncio
import logging
from typing import Any

import pytest

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_manager import SimulationManager
from tests.services.simulation_fakes import NOW, Harness, until_cancelled

R = RequestStatus
S = SimulationStatus


async def test_start_returns_at_once_and_the_run_goes_on_in_the_background() -> None:
    h = Harness(count=2)
    manager = SimulationManager(h.deps)

    manager.start(h.job)

    # 요청은 여기서 바로 응답할 수 있다. 모델 호출은 아직 시작도 하지 않았다
    assert h.caller.calls == []
    assert manager.active_count == 1

    await manager.wait_idle()

    assert h.store.finished == [(S.SUCCESS, NOW)]
    assert set(h.recorder.statuses.values()) == {R.SUCCESS}


async def test_a_run_is_kept_until_it_finishes_and_then_forgotten() -> None:
    started = asyncio.Event()
    h = Harness(count=1)
    h.caller.behaviors = {h.model(1): until_cancelled(started)}
    manager = SimulationManager(h.deps)

    manager.start(h.job)
    await asyncio.wait_for(started.wait(), timeout=1)
    assert manager.active_count == 1
    assert manager.registry.is_active(h.job.simulation_id)

    manager.registry.signal(h.request_id(1))
    await manager.wait_idle()

    assert manager.active_count == 0
    assert not manager.registry.is_active(h.job.simulation_id)


async def test_the_cancel_signal_of_a_running_call_reaches_it() -> None:
    started = asyncio.Event()
    h = Harness(count=3)
    h.caller.behaviors = {h.model(2): until_cancelled(started)}
    manager = SimulationManager(h.deps)

    manager.start(h.job)
    await asyncio.wait_for(started.wait(), timeout=1)
    manager.registry.signal(h.request_id(2))
    await manager.wait_idle()

    assert h.store.finished == [(S.PARTIAL_SUCCESS, NOW)]
    assert h.recorder.statuses[h.request_id(2)] == R.CANCELLED


async def test_runs_do_not_wait_for_each_other() -> None:
    started = asyncio.Event()
    slow = Harness(count=1)
    slow.caller.behaviors = {slow.model(1): until_cancelled(started)}
    fast = Harness(count=1)
    manager = SimulationManager(slow.deps)
    other = SimulationManager(fast.deps, registry=manager.registry)

    manager.start(slow.job)
    await asyncio.wait_for(started.wait(), timeout=1)
    other.start(fast.job)
    await other.wait_idle()

    assert fast.store.finished == [(S.SUCCESS, NOW)]
    assert manager.active_count == 1  # 느린 쪽은 아직 돈다
    manager.registry.signal(slow.request_id(1))
    await manager.wait_idle()


async def test_a_crashing_run_is_contained_logged_and_cleaned_up(
    caplog: pytest.LogCaptureFixture,
) -> None:
    h = Harness(count=1)

    async def broken_start(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("sk-secret-key")

    h.store.mark_started = broken_start  # type: ignore[method-assign]
    manager = SimulationManager(h.deps)

    with caplog.at_level(logging.ERROR):
        manager.start(h.job)
        await manager.wait_idle()  # 오류가 호출한 쪽으로 번지지 않는다

    assert manager.active_count == 0
    assert not manager.registry.is_active(h.job.simulation_id)
    # 로그에는 실행 ID 와 예외 종류만 남기고 예외 메시지(키가 들어갈 수 있다)는 남기지 않는다
    assert str(h.job.simulation_id) in caplog.text
    assert "RuntimeError" in caplog.text
    assert "sk-secret-key" not in caplog.text


async def test_wait_idle_with_nothing_running_returns_at_once() -> None:
    manager = SimulationManager(Harness(count=1).deps)

    await asyncio.wait_for(manager.wait_idle(), timeout=1)

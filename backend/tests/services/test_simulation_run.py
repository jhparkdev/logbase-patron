import asyncio
import uuid
from typing import Any

import pytest

from app.models import CostStatus, ErrorType, RequestStatus, SimulationStatus
from app.services.simulation_input import SIMULATION_TIMEOUT_SECONDS
from app.services.simulation_ports import ModelCallResult
from app.services.simulation_run import run_simulation
from tests.services.simulation_fakes import (
    NOW,
    Harness,
    failed,
    never_finishes,
    ok,
    until_cancelled,
)

R = RequestStatus
S = SimulationStatus
SCHEMA = {"type": "object", "required": ["title"]}


async def test_all_models_succeed() -> None:
    h = Harness(count=3)

    status = await run_simulation(h.job, h.deps)

    assert status == S.SUCCESS
    assert set(h.recorder.statuses.values()) == {R.SUCCESS}
    assert h.store.started == [NOW]
    assert h.store.finished == [(S.SUCCESS, NOW)]


async def test_every_model_gets_the_same_input_and_its_own_pinned_provider() -> None:
    h = Harness(
        count=2,
        json_schema=SCHEMA,
        allow_fallbacks=True,
        execution_config={"temperature": 0.2, "max_tokens": 512},
    )

    await run_simulation(h.job, h.deps)

    calls = {call["model"]: call for call in h.caller.calls}
    assert set(calls) == {h.model(1), h.model(2)}
    for slot in h.slots:
        call = calls[slot.openrouter_model_id]
        assert call["messages"] == h.messages
        assert call["provider_order"] == [slot.execution_provider]
        assert call["allow_fallbacks"] is True
        assert call["json_schema"] == SCHEMA
        assert call["execution_config"] == {"temperature": 0.2, "max_tokens": 512}
        assert call["timeout_seconds"] == SIMULATION_TIMEOUT_SECONDS
        assert isinstance(call["cancel"], asyncio.Event)


async def test_models_are_called_in_parallel() -> None:
    # 한 모델씩 차례로 부르면 서로를 기다리다가 시간 초과로 실패한다
    h = Harness(count=4)
    arrived = 0
    all_arrived = asyncio.Event()

    async def wait_for_the_others(kwargs: dict[str, Any]) -> ModelCallResult:
        nonlocal arrived
        arrived += 1
        if arrived == 4:
            all_arrived.set()
        await asyncio.wait_for(all_arrived.wait(), timeout=1)
        return ok()

    h.caller.behaviors = {
        slot.openrouter_model_id: wait_for_the_others for slot in h.slots
    }

    assert await run_simulation(h.job, h.deps) == S.SUCCESS


async def test_one_timeout_leaves_the_other_results_and_is_partial_success() -> None:
    # T-10, T-21
    async def timeout(kwargs: dict[str, Any]) -> ModelCallResult:
        return failed(R.TIMEOUT)

    h = Harness(count=3)
    h.caller.behaviors = {h.model(2): timeout}

    status = await run_simulation(h.job, h.deps)

    assert status == S.PARTIAL_SUCCESS
    assert h.recorder.statuses[h.request_id(1)] == R.SUCCESS
    assert h.recorder.statuses[h.request_id(2)] == R.TIMEOUT
    assert h.recorder.statuses[h.request_id(3)] == R.SUCCESS
    timed_out = h.recorder.records[h.request_id(2)]
    assert timed_out.error_type == ErrorType.TIMEOUT_ERROR
    assert (timed_out.cost_status, timed_out.cost_usd) == (CostStatus.UNKNOWN, None)


async def test_an_unexpected_error_fails_only_that_slot() -> None:
    async def boom(kwargs: dict[str, Any]) -> ModelCallResult:
        raise RuntimeError("예상 밖 오류")

    h = Harness(count=3)
    h.caller.behaviors = {h.model(1): boom}

    status = await run_simulation(h.job, h.deps)

    assert status == S.PARTIAL_SUCCESS
    record = h.recorder.records[h.request_id(1)]
    assert (record.status, record.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)
    assert (record.cost_status, record.cost_usd) == (CostStatus.UNKNOWN, None)
    assert h.recorder.statuses[h.request_id(2)] == R.SUCCESS


async def test_the_error_message_is_not_stored_for_the_user() -> None:
    # 예외 메시지에는 내부 정보나 키가 들어 있을 수 있어 기록에 옮기지 않는다
    async def boom(kwargs: dict[str, Any]) -> ModelCallResult:
        raise RuntimeError("sk-secret-key")

    h = Harness(count=2)
    h.caller.behaviors = {h.model(1): boom}

    await run_simulation(h.job, h.deps)

    assert "sk-secret-key" not in repr(h.recorder.records)


async def test_all_models_fail_is_failed() -> None:
    async def fail(kwargs: dict[str, Any]) -> ModelCallResult:
        return failed()

    h = Harness(count=2)
    h.caller.behaviors = {h.model(1): fail, h.model(2): fail}

    assert await run_simulation(h.job, h.deps) == S.FAILED
    assert h.store.finished == [(S.FAILED, NOW)]


async def test_response_text_and_validation_are_saved_for_each_finished_slot() -> None:
    h = Harness(count=2, json_schema=SCHEMA)

    async def bad_json(kwargs: dict[str, Any]) -> ModelCallResult:
        return ok("JSON 아님")

    h.caller.behaviors = {h.model(1): bad_json}

    status = await run_simulation(h.job, h.deps)

    assert status == S.SUCCESS  # API 호출은 성공했고 검증만 실패한다
    assert h.recorder.payloads[h.request_id(1)] == (h.messages, "JSON 아님")
    assert h.store.validations[h.request_id(1)].json_parse_status.value == "FAILED"
    assert h.store.validations[h.request_id(2)].json_parse_status.value == "FAILED"


# --- 취소 ---


async def test_cancel_signal_stops_only_that_model() -> None:
    started = asyncio.Event()
    h = Harness(count=3)
    h.caller.behaviors = {h.model(2): until_cancelled(started)}
    cancel_events = {slot.request_id: asyncio.Event() for slot in h.slots}

    task = asyncio.create_task(
        run_simulation(h.job, h.deps, cancel_events=cancel_events)
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    cancel_events[h.request_id(2)].set()

    assert await asyncio.wait_for(task, timeout=1) == S.PARTIAL_SUCCESS
    assert h.recorder.statuses[h.request_id(2)] == R.CANCELLED
    assert h.recorder.statuses[h.request_id(1)] == R.SUCCESS


async def test_cancelling_every_model_ends_the_run_as_cancelled() -> None:
    started = asyncio.Event()
    h = Harness(count=2)
    h.caller.behaviors = {
        slot.openrouter_model_id: until_cancelled(started) for slot in h.slots
    }
    cancel_events = {slot.request_id: asyncio.Event() for slot in h.slots}

    task = asyncio.create_task(
        run_simulation(h.job, h.deps, cancel_events=cancel_events)
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    for event in cancel_events.values():
        event.set()

    assert await asyncio.wait_for(task, timeout=1) == S.CANCELLED
    assert h.store.finished == [(S.CANCELLED, NOW)]


async def test_a_slot_cancelled_before_it_starts_is_never_called() -> None:
    h = Harness(count=3)
    assert await h.recorder.cancel_if_open(h.request_id(2), NOW)

    status = await run_simulation(h.job, h.deps)

    assert status == S.PARTIAL_SUCCESS
    assert h.model(2) not in {call["model"] for call in h.caller.calls}
    assert h.recorder.statuses[h.request_id(2)] == R.CANCELLED


async def test_a_response_that_arrives_after_cancel_does_not_change_the_cancelled_slot() -> (
    None
):
    # 종료된 호출의 상태는 바꾸지 않는다. 늦게 온 결과는 저장하지 않는다
    gate = asyncio.Event()
    started = asyncio.Event()
    h = Harness(count=2)

    async def late_success(kwargs: dict[str, Any]) -> ModelCallResult:
        started.set()
        await gate.wait()
        return ok("늦은 응답")

    h.caller.behaviors = {h.model(1): late_success}

    task = asyncio.create_task(run_simulation(h.job, h.deps))
    await asyncio.wait_for(started.wait(), timeout=1)
    assert await h.recorder.cancel_if_open(h.request_id(1), NOW)
    gate.set()

    assert await asyncio.wait_for(task, timeout=1) == S.PARTIAL_SUCCESS
    assert h.recorder.statuses[h.request_id(1)] == R.CANCELLED
    assert h.request_id(1) not in h.recorder.payloads
    assert h.request_id(1) not in h.store.validations


# --- 하트비트와 끝나지 않은 실행 ---


async def test_heartbeat_is_recorded_while_running_and_stops_at_the_end() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()
    h = Harness(count=1)

    async def slow(kwargs: dict[str, Any]) -> ModelCallResult:
        started.set()
        await gate.wait()
        return ok()

    h.caller.behaviors = {h.model(1): slow}

    task = asyncio.create_task(
        run_simulation(h.job, h.deps, heartbeat_interval_seconds=0.01)
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.05)
    assert len(h.store.heartbeats) >= 1

    gate.set()
    await asyncio.wait_for(task, timeout=1)
    count = len(h.store.heartbeats)
    await asyncio.sleep(0.05)
    assert len(h.store.heartbeats) == count


async def test_a_slot_that_could_not_be_recorded_leaves_the_run_for_recovery() -> None:
    # 결과 저장이 실패하면 그 칸은 RUNNING 으로 남는다. 실행을 끝난 것으로 표시하지 않고 복구(8단계)에 맡긴다
    h = Harness(count=2)
    h.recorder.fail_on_record = {h.request_id(1)}

    status = await run_simulation(h.job, h.deps)

    assert status == S.RUNNING
    assert h.store.finished == []
    assert h.recorder.statuses[h.request_id(2)] == R.SUCCESS


async def test_cancelling_the_whole_task_does_not_mark_the_run_finished() -> None:
    # 서버가 내려가는 경우. 끝난 것처럼 기록하지 않는다
    started = asyncio.Event()
    h = Harness(count=2)
    h.caller.behaviors = {
        slot.openrouter_model_id: never_finishes(started) for slot in h.slots
    }

    task = asyncio.create_task(run_simulation(h.job, h.deps))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert h.store.finished == []


def test_job_carries_the_ids_needed_to_run() -> None:
    h = Harness(count=2)

    assert isinstance(h.job.simulation_id, uuid.UUID)
    assert [slot.slot_no for slot in h.job.slots] == [1, 2]

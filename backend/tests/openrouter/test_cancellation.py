import asyncio

import pytest

from app.openrouter.cancellation import run_unless_cancelled

HANG_SECONDS = 3600


class Worker:
    """끝나지 않고 기다리는 작업. 멈춰졌는지 기록한다."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.was_cancelled = False

    async def hang(self) -> str:
        self.started.set()
        try:
            await asyncio.sleep(HANG_SECONDS)
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise
        return "done"


async def quick(value: str) -> str:
    return value


async def raise_error() -> str:
    raise ValueError("작업이 실패했다")


def only_current_task_is_left() -> bool:
    """테스트 자기 자신 말고 남아 있는 작업이 없는지 본다."""
    return len(asyncio.all_tasks()) == 1


async def test_작업이_먼저_끝나면_작업_결과를_돌려준다() -> None:
    result = await run_unless_cancelled(quick("ok"), asyncio.Event())

    assert result == "ok"
    assert only_current_task_is_left()


async def test_취소_신호가_먼저_켜지면_None을_돌려주고_작업을_멈춘다() -> None:
    worker = Worker()
    cancel = asyncio.Event()

    task = asyncio.create_task(run_unless_cancelled(worker.hang(), cancel))
    await worker.started.wait()
    cancel.set()
    result = await task

    assert result is None
    assert worker.was_cancelled is True
    assert only_current_task_is_left()


async def test_같은_순간이면_취소_신호보다_작업_결과를_우선한다() -> None:
    cancel = asyncio.Event()
    cancel.set()

    result = await run_unless_cancelled(quick("ok"), cancel)

    assert result == "ok"


async def test_작업에서_난_예외는_그대로_올린다() -> None:
    with pytest.raises(ValueError, match="작업이 실패했다"):
        await run_unless_cancelled(raise_error(), asyncio.Event())

    assert only_current_task_is_left()


async def test_바깥에서_취소되면_CancelledError를_올리고_안쪽_작업도_멈춘다() -> None:
    worker = Worker()

    task = asyncio.create_task(run_unless_cancelled(worker.hang(), asyncio.Event()))
    await worker.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert worker.was_cancelled is True
    assert only_current_task_is_left()

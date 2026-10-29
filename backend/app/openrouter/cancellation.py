"""작업 하나를 취소 신호와 겨루어 실행한다."""

import asyncio
from collections.abc import Coroutine
from typing import Any


async def run_unless_cancelled[T](
    work: Coroutine[Any, Any, T], cancel: asyncio.Event
) -> T | None:
    """work를 실행하되, 취소 신호가 먼저 켜지면 work를 멈추고 None을 돌려준다.

    work가 먼저 끝났거나 같은 순간에 끝났으면 취소 신호보다 work의 결과를 우선한다.
    work에서 난 예외는 그대로 올린다.
    """
    work_task = asyncio.create_task(work)
    cancel_task = asyncio.create_task(cancel.wait())
    try:
        await asyncio.wait(
            {work_task, cancel_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if work_task.done():
            return work_task.result()
        return None
    finally:
        # 끝나지 않은 작업은 멈추고 정리가 끝날 때까지 기다린다.
        # 이 함수 자체가 바깥에서 취소돼도 안쪽 작업이 남지 않게 한다.
        work_task.cancel()
        cancel_task.cancel()
        await asyncio.gather(work_task, cancel_task, return_exceptions=True)

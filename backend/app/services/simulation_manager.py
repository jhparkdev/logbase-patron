"""백그라운드 실행 작업을 시작하고 붙들고 정리하는 작업 관리자.

요청이 응답한 뒤에도 모델 호출은 계속 돌아야 해서 요청과 별개의 asyncio 작업으로 띄운다.
이 관리자가 하는 일은 세 가지다.
- 작업 참조를 들고 있는다. 아무도 들고 있지 않은 작업은 도중에 치워질 수 있다(Python 문서의 경고).
- 취소 신호 보관함(CancelRegistry)을 같이 들고 있어서 취소 요청이 돌고 있는 호출을 찾을 수 있다.
- 작업이 예외로 끝나도 요청으로 번지지 않게 가두고, 실행 ID 와 예외 종류만 로그에 남긴다.

backend 는 인스턴스 1대로 띄우는 것을 전제로 한다(backend/CLAUDE.md). 서버가 내려가면 도중의 작업은
사라지고, DB 에 남은 PENDING·RUNNING 은 시작 때의 복구 작업이 정리한다.
"""

import asyncio
import logging
import uuid

from app.services.simulation_ports import SimulationDeps, SimulationJob
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_run import run_registered_simulation

# 로그에는 실행 ID 와 예외 종류만 남긴다. 예외 메시지에는 키나 내부 정보가 들어갈 수 있다
logger = logging.getLogger(__name__)


class SimulationManager:
    def __init__(
        self, deps: SimulationDeps, registry: CancelRegistry | None = None
    ) -> None:
        self._deps = deps
        self.registry = registry or CancelRegistry()
        self._tasks: set[asyncio.Task[object]] = set()

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    def start(self, job: SimulationJob) -> None:
        """실행을 백그라운드로 시작하고 바로 돌아온다. 호출하는 쪽은 저장을 commit 한 뒤에 불러야 한다."""
        task = asyncio.create_task(
            run_registered_simulation(job, self._deps, self.registry)
        )
        self._tasks.add(task)
        task.add_done_callback(
            lambda finished: self._forget(job.simulation_id, finished)
        )

    async def wait_idle(self) -> None:
        """돌고 있는 실행이 모두 끝날 때까지 기다린다. 테스트와 종료 처리에서 쓴다."""
        while self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def _forget(self, simulation_id: uuid.UUID, task: asyncio.Task[object]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()  # 꺼내 두어야 "처리되지 않은 예외" 경고가 나지 않는다
        if error is not None:
            logger.error(
                "simulation run crashed: simulation_id=%s error=%s",
                simulation_id,
                type(error).__name__,
            )

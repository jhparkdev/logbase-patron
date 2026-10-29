"""시뮬레이터 라우터가 쓰는 의존성."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.deps import NowDep
from app.db import get_sessionmaker
from app.services.simulation_cancel_service import CancelDeps
from app.services.simulation_manager import SimulationManager
from app.services.simulation_ports import ModelCaller, SimulationDeps
from app.services.simulation_recorders import ScopedRequestRecorder
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_scoped_store import ScopedSimulationStore


def get_model_caller() -> ModelCaller:
    """모델을 부르는 함수(OpenRouterClient.call_model).

    OpenRouter Key 설정과 클라이언트를 만들어 주입하는 일은 정욱님 몫이라 아직 연결되지 않았다.
    그 전에는 실행을 받지 않는다. 의존성이 저장보다 먼저 풀리므로 아무것도 저장되지 않는다.
    """
    raise RuntimeError("OpenRouter 클라이언트가 아직 연결되지 않았다")


@lru_cache
def get_cancel_registry() -> CancelRegistry:
    """돌고 있는 호출의 취소 신호 보관함. 프로세스에 하나만 두어 실행과 취소 요청이 같은 것을 본다."""
    return CancelRegistry()


@lru_cache
def get_simulation_manager() -> SimulationManager:
    """프로세스에 하나만 둔다. 모델 호출기가 연결되어야 만들어진다.

    테스트는 app.dependency_overrides 로 바꿔 끼운다.
    """
    sessions = get_sessionmaker()
    return SimulationManager(
        SimulationDeps(
            caller=get_model_caller(),
            recorder=ScopedRequestRecorder(sessions),
            store=ScopedSimulationStore(sessions),
            now=lambda: datetime.now(UTC),
        ),
        registry=get_cancel_registry(),
    )


def get_cancel_deps(now: NowDep) -> CancelDeps:
    """취소에 필요한 것. 모델 호출기와 무관해서 OpenRouter 가 연결되기 전에도 취소할 수 있다.

    쓸 때마다 새 세션을 열고 commit 하므로, CANCELLED 가 확정된 뒤에 멈춤 신호가 켜진다.
    """
    sessions = get_sessionmaker()
    return CancelDeps(
        store=ScopedSimulationStore(sessions),
        recorder=ScopedRequestRecorder(sessions),
        registry=get_cancel_registry(),
        now=lambda: now,
    )


SimulationManagerDep = Annotated[SimulationManager, Depends(get_simulation_manager)]
CancelDepsDep = Annotated[CancelDeps, Depends(get_cancel_deps)]

"""시뮬레이터 라우터가 쓰는 의존성."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.db import get_sessionmaker
from app.services.simulation_manager import SimulationManager
from app.services.simulation_ports import ModelCaller, SimulationDeps
from app.services.simulation_recorders import ScopedRequestRecorder
from app.services.simulation_scoped_store import ScopedSimulationStore


def get_model_caller() -> ModelCaller:
    """모델을 부르는 함수(OpenRouterClient.call_model).

    OpenRouter Key 설정과 클라이언트를 만들어 주입하는 일은 정욱님 몫이라 아직 연결되지 않았다.
    그 전에는 실행을 받지 않는다. 의존성이 저장보다 먼저 풀리므로 아무것도 저장되지 않는다.
    """
    raise RuntimeError("OpenRouter 클라이언트가 아직 연결되지 않았다")


@lru_cache
def get_simulation_manager() -> SimulationManager:
    """프로세스에 하나만 둔다. 돌고 있는 실행과 취소 신호가 한곳에 모여 있어야 취소 요청이 찾을 수 있다.

    테스트는 app.dependency_overrides 로 바꿔 끼운다.
    """
    sessions = get_sessionmaker()
    return SimulationManager(
        SimulationDeps(
            caller=get_model_caller(),
            recorder=ScopedRequestRecorder(sessions),
            store=ScopedSimulationStore(sessions),
            now=lambda: datetime.now(UTC),
        )
    )


SimulationManagerDep = Annotated[SimulationManager, Depends(get_simulation_manager)]

"""시뮬레이터 라우터가 쓰는 의존성."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends
from pydantic import SecretStr

from app.api.deps import NowDep, SettingsDep
from app.db import get_sessionmaker
from app.openrouter.client import OpenRouterClient
from app.services.simulation_cancel_service import CancelDeps
from app.services.simulation_manager import SimulationManager
from app.services.simulation_ports import ModelCaller, SimulationDeps
from app.services.simulation_recorders import ScopedRequestRecorder
from app.services.simulation_registry import CancelRegistry
from app.services.simulation_scoped_store import ScopedSimulationStore


def get_model_caller(api_key: SecretStr | None) -> ModelCaller:
    """모델을 부르는 함수(OpenRouterClient.call_model).

    Key 가 없으면 실행을 받지 않는다. 의존성이 저장보다 먼저 풀리므로 아무것도 저장되지 않는다.
    """
    # 값만 지운 줄(OPENROUTER_API_KEY=)은 빈 문자열로 읽히므로 없는 것과 같이 본다
    if api_key is None or not api_key.get_secret_value():
        raise RuntimeError(
            "OPENROUTER_API_KEY 가 설정되지 않아 비교 실행을 받을 수 없다"
        )
    # 클라이언트는 _shared_manager 가 프로세스에 하나만 만들므로 앱 수명 동안 재사용된다
    client = OpenRouterClient(
        http_client=httpx.AsyncClient(), api_key=api_key.get_secret_value()
    )
    return client.call_model


@lru_cache
def get_cancel_registry() -> CancelRegistry:
    """돌고 있는 호출의 취소 신호 보관함. 프로세스에 하나만 두어 실행과 취소 요청이 같은 것을 본다."""
    return CancelRegistry()


def get_simulation_manager(settings: SettingsDep) -> SimulationManager:
    """설정을 의존성으로 받아, 테스트가 바꿔 끼운 설정(Key 없음)을 따르게 한다.

    테스트는 app.dependency_overrides 로 바꿔 끼운다.
    """
    return _shared_manager(settings.openrouter_api_key)


@lru_cache
def _shared_manager(api_key: SecretStr | None) -> SimulationManager:
    """프로세스에 하나만 둔다. 모델 호출기가 연결되어야 만들어진다."""
    sessions = get_sessionmaker()
    return SimulationManager(
        SimulationDeps(
            caller=get_model_caller(api_key),
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

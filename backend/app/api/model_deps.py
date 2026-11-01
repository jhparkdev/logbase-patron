"""모델 관리(P-03) 라우터가 쓰는 의존성."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends
from pydantic import SecretStr

from app.api.deps import SettingsDep
from app.openrouter.client import OpenRouterClient
from app.services.model_test import ConnectionCaller
from app.services.openrouter_catalog import OpenRouterCatalog


@lru_cache
def get_openrouter_catalog() -> OpenRouterCatalog:
    """프로세스에 하나만 둔다. 보관한 목록을 모든 요청이 함께 쓰기 위해서다.

    모델 목록 조회는 공개 API라 Key 없이 부른다. 테스트는 app.dependency_overrides로 바꿔 끼운다.
    """
    client = OpenRouterClient(http_client=httpx.AsyncClient(), api_key="")
    return OpenRouterCatalog(fetch=client.list_models, now=lambda: datetime.now(UTC))


CatalogDep = Annotated[OpenRouterCatalog, Depends(get_openrouter_catalog)]


@lru_cache
def _shared_caller(api_key: SecretStr) -> ConnectionCaller:
    """프로세스에 하나만 둔다. 클라이언트를 앱 수명 동안 재사용한다."""
    client = OpenRouterClient(
        http_client=httpx.AsyncClient(), api_key=api_key.get_secret_value()
    )
    return client.call_model


def get_connection_caller(settings: SettingsDep) -> ConnectionCaller | None:
    """연결 테스트에 쓸 모델 호출기. Key가 없거나 비어 있으면 None이다.

    테스트는 app.dependency_overrides로 바꿔 끼운다.
    """
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        return None
    return _shared_caller(key)


ConnectionCallerDep = Annotated[ConnectionCaller | None, Depends(get_connection_caller)]

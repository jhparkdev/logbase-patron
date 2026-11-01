"""모델 관리(P-03) 라우터가 쓰는 의존성."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.openrouter.client import OpenRouterClient
from app.services.openrouter_catalog import OpenRouterCatalog


@lru_cache
def get_openrouter_catalog() -> OpenRouterCatalog:
    """프로세스에 하나만 둔다. 보관한 목록을 모든 요청이 함께 쓰기 위해서다.

    모델 목록 조회는 공개 API라 Key 없이 부른다. 테스트는 app.dependency_overrides로 바꿔 끼운다.
    """
    client = OpenRouterClient(http_client=httpx.AsyncClient(), api_key="")
    return OpenRouterCatalog(fetch=client.list_models, now=lambda: datetime.now(UTC))


CatalogDep = Annotated[OpenRouterCatalog, Depends(get_openrouter_catalog)]

"""OpenRouter 모델 목록을 잠시 보관한다.

목록은 약 470개, 800KB 남짓이라 검색할 때마다 새로 받지 않는다.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from app.openrouter.lookup_result import LookupResult, ModelInfo

CACHE_TTL = timedelta(minutes=10)

FetchModels = Callable[[], Awaitable[LookupResult[list[ModelInfo]]]]

logger = logging.getLogger(__name__)


class OpenRouterUnavailableError(Exception):
    """보관한 목록이 없는데 OpenRouter에서도 목록을 받지 못했다."""


class OpenRouterCatalog:
    def __init__(self, fetch: FetchModels, now: Callable[[], datetime]) -> None:
        self._fetch = fetch
        self._now = now
        self._models: list[ModelInfo] | None = None
        self._fetched_at: datetime | None = None
        # 동시에 들어온 요청이 목록을 여러 번 받지 않게 한 번에 하나만 새로 받는다.
        self._lock = asyncio.Lock()

    async def get(self) -> list[ModelInfo]:
        """보관한 목록을 돌려준다. 10분이 지났으면 새로 받고, 받지 못하면 보관한 목록을 그대로 쓴다."""
        async with self._lock:
            fresh = self._fresh_models()
            if fresh is not None:
                return fresh

            result = await self._fetch()
            # 빈 목록은 조회가 잘못된 것으로 보고 받아들이지 않는다.
            if result.ok and result.data:
                self._models = result.data
                self._fetched_at = self._now()
            else:
                logger.warning(
                    "openrouter model list refresh failed error_type=%s",
                    result.error_type,
                )

            if self._models is None:
                raise OpenRouterUnavailableError
            return self._models

    def _fresh_models(self) -> list[ModelInfo] | None:
        if self._models is None or self._fetched_at is None:
            return None
        if self._now() - self._fetched_at >= CACHE_TTL:
            return None
        return self._models

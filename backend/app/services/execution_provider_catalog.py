"""모델별 서버 업체(execution provider) 목록을 잠시 보관한다(P-03).

업체 목록은 모델마다 OpenRouter에 따로 물어야 한다. 화면이 같은 모델을 자주 열 수 있어
모델별로 10분 동안 보관한다. 물어보는 모델은 등록된 모델뿐이라 보관하는 개수가 늘어나는 데 한도가 있다.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus

from app.openrouter.lookup_result import EndpointInfo, LookupResult
from app.services.openrouter_catalog import CACHE_TTL, OpenRouterUnavailableError

FetchEndpoints = Callable[[str], Awaitable[LookupResult[list[EndpointInfo]]]]

logger = logging.getLogger(__name__)


class ModelNotOnOpenRouterError(LookupError):
    """OpenRouter가 이 모델을 모른다고 답했다."""


@dataclass(frozen=True)
class _Entry:
    endpoints: list[EndpointInfo]
    fetched_at: datetime


class EndpointCatalog:
    def __init__(self, fetch: FetchEndpoints, now: Callable[[], datetime]) -> None:
        self._fetch = fetch
        self._now = now
        self._entries: dict[str, _Entry] = {}
        # 같은 모델을 동시에 여러 번 묻지 않게 한 번에 하나만 새로 받는다. 모델 사이에도 순서대로 처리한다.
        self._lock = asyncio.Lock()

    async def get(self, openrouter_model_id: str) -> list[EndpointInfo]:
        """모델을 처리하는 업체 목록을 돌려준다.

        10분이 지났으면 새로 받는다. 받지 못하면 보관한 목록을 그대로 쓰고, 보관한 것도 없으면
        OpenRouterUnavailableError다. OpenRouter가 모델이 없다고 답하면 보관한 목록을 지우고
        ModelNotOnOpenRouterError다.
        """
        async with self._lock:
            entry = self._entries.get(openrouter_model_id)
            if entry is not None and self._now() - entry.fetched_at < CACHE_TTL:
                return entry.endpoints

            result = await self._fetch(openrouter_model_id)
            if result.ok and result.data is not None:
                self._entries[openrouter_model_id] = _Entry(result.data, self._now())
                return result.data

            if result.http_status == HTTPStatus.NOT_FOUND:
                self._entries.pop(openrouter_model_id, None)
                raise ModelNotOnOpenRouterError

            logger.warning(
                "openrouter endpoints refresh failed error_type=%s", result.error_type
            )
            if entry is None:
                raise OpenRouterUnavailableError
            return entry.endpoints

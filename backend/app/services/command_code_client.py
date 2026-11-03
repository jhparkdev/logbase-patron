"""Command Code 사용량 조회. 비공식 API(공식 문서 없음)라 응답이 예고 없이 바뀔 수 있다.

조회는 실패해도 예외를 던지지 않고 FetchResult로 돌려준다. 로그에는 경로와 상태 코드만 남기고
Key, 응답 본문, 예외 문구는 남기지 않는다.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.openrouter.parsing import loads_decimal
from app.schemas.command_code import CommandCodeStatus
from app.services.command_code_parsing import classify_error, parse_snapshot
from app.services.command_code_result import FetchResult

BASE_URL = "https://api.commandcode.ai"
# 순서: 사용량 요약, 크레딧, 구독. parse_snapshot이 받는 순서와 같다.
PATHS = (
    "/alpha/usage/summary",
    "/alpha/billing/credits",
    "/alpha/billing/subscriptions",
)
# 이 헤더가 없으면 403이 난다고 Command Code 개발자가 알려 줬다
USER_AGENT = "logbase-patron"
TIMEOUT_SECONDS = 10.0

logger = logging.getLogger(__name__)

_Reply = tuple[int, Any]


class CommandCodeClient:
    """Key 하나로 세 곳을 부른다. httpx 클라이언트는 앱 수명 동안 하나를 재사용한다."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def fetch(self, api_key: str) -> FetchResult:
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT}
        replies = await asyncio.gather(*(self._get(path, headers) for path in PATHS))
        bodies: list[Any] = []
        for path, reply in zip(PATHS, replies, strict=True):
            if reply is None:
                return FetchResult(status=CommandCodeStatus.FETCH_FAILED)
            status_code, body = reply
            if status_code != httpx.codes.OK:
                logger.warning(
                    "Command Code 조회 실패 path=%s status=%s", path, status_code
                )
                return FetchResult(status=classify_error(status_code, body))
            bodies.append(body)
        snapshot = parse_snapshot(*bodies)
        if snapshot is None:
            logger.warning("Command Code 응답을 읽지 못함 (예상과 다른 모양)")
            return FetchResult(status=CommandCodeStatus.FETCH_FAILED)
        return FetchResult(status=CommandCodeStatus.OK, snapshot=snapshot)

    async def _get(self, path: str, headers: dict[str, str]) -> _Reply | None:
        try:
            response = await self._http.get(
                BASE_URL + path, headers=headers, timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as error:
            logger.warning(
                "Command Code 연결 실패 path=%s error=%s", path, type(error).__name__
            )
            return None
        try:
            body = loads_decimal(response.text)
        except ValueError:
            body = None
        return response.status_code, body

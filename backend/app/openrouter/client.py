"""OpenRouter를 부르는 유일한 곳.

call_model은 실패해도 예외를 던지지 않고 실패 결과(CallResult)를 돌려준다.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from app.openrouter.cancellation import run_unless_cancelled
from app.openrouter.errors import (
    ErrorType,
    classify_http_error,
    get_failed_routing_step,
)
from app.openrouter.failures import build_cancelled_result, build_failure_result
from app.openrouter.parsing import build_result_from_chat_body, loads_decimal
from app.openrouter.request import build_request_body
from app.openrouter.result import CallResult, CallStatus

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _read_json(response: httpx.Response) -> Any:
    """응답 본문을 JSON으로 읽는다. JSON이 아니면 None."""
    try:
        return loads_decimal(response.text)
    except ValueError:
        return None


class OpenRouterClient:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        api_key: str,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key
        self._clock = clock

    async def call_model(
        self,
        *,
        request_id: UUID,
        model_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        timeout_seconds: float,
        json_schema: dict[str, Any] | None = None,
        provider_order: list[str] | None = None,
        allow_fallbacks: bool = False,
        cancel: asyncio.Event | None = None,
    ) -> CallResult:
        """모델을 호출하고 결과를 돌려준다. 실패해도 예외를 던지지 않는다.

        cancel 신호가 켜지면 호출을 멈추고 CANCELLED 결과를 돌려준다.
        신호가 없으면(None) 취소하지 않는다.
        """
        started_at = self._clock()
        request_body = build_request_body(
            model_id=model_id,
            messages=messages,
            max_tokens=max_tokens,
            json_schema=json_schema,
            provider_order=provider_order,
            allow_fallbacks=allow_fallbacks,
        )

        if cancel is not None and cancel.is_set():
            # 이미 취소 신호가 켜져 있으면 요청을 보내지 않는다.
            result = self._cancelled(model_id, started_at)
        else:
            result = await self._send(
                request_body, model_id, timeout_seconds, cancel, started_at
            )

        # 로그에는 호출 ID와 결과 상태만 남긴다. Key, Prompt, 응답 원문은 쓰지 않는다.
        logger.info(
            "openrouter call finished request_id=%s status=%s http_status=%s",
            request_id,
            result.status,
            result.http_status,
        )
        return result

    async def _send(
        self,
        request_body: dict[str, Any],
        model_id: str,
        timeout_seconds: float,
        cancel: asyncio.Event | None,
        started_at: datetime,
    ) -> CallResult:
        # 비용이 드는 호출이라 실패해도 자동으로 다시 보내지 않는다.
        try:
            response = await self._post(request_body, timeout_seconds, cancel)
        except httpx.TimeoutException:
            return self._failure(
                CallStatus.TIMEOUT, ErrorType.TIMEOUT_ERROR, model_id, started_at
            )
        except httpx.RequestError:
            return self._failure(
                CallStatus.FAILED, ErrorType.NETWORK_ERROR, model_id, started_at
            )

        if response is None:
            return self._cancelled(model_id, started_at)
        return self._result_from_response(response, model_id, started_at)

    async def _post(
        self,
        request_body: dict[str, Any],
        timeout_seconds: float,
        cancel: asyncio.Event | None,
    ) -> httpx.Response | None:
        """요청을 보낸다. 보내는 도중 취소 신호가 켜지면 연결을 끊고 None을 돌려준다."""
        work = self._http_client.post(
            CHAT_COMPLETIONS_URL,
            json=request_body,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=timeout_seconds,
        )
        if cancel is None:
            return await work
        return await run_unless_cancelled(work, cancel)

    def _cancelled(self, model_id: str, started_at: datetime) -> CallResult:
        return build_cancelled_result(
            requested_model=model_id,
            started_at=started_at,
            finished_at=self._clock(),
        )

    def _failure(
        self,
        status: CallStatus,
        error_type: ErrorType,
        model_id: str,
        started_at: datetime,
    ) -> CallResult:
        return build_failure_result(
            status=status,
            error_type=error_type,
            requested_model=model_id,
            started_at=started_at,
            finished_at=self._clock(),
        )

    def _result_from_response(
        self, response: httpx.Response, model_id: str, started_at: datetime
    ) -> CallResult:
        finished_at = self._clock()
        body = _read_json(response)

        if response.is_success:
            if not isinstance(body, dict):
                return build_failure_result(
                    status=CallStatus.FAILED,
                    error_type=ErrorType.INVALID_RESPONSE,
                    requested_model=model_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    http_status=response.status_code,
                )
            return build_result_from_chat_body(
                body,
                requested_model=model_id,
                started_at=started_at,
                finished_at=finished_at,
                http_status=response.status_code,
            )

        error_body = body if isinstance(body, dict) else None
        return build_failure_result(
            status=CallStatus.FAILED,
            error_type=classify_http_error(response.status_code, error_body),
            requested_model=model_id,
            started_at=started_at,
            finished_at=finished_at,
            http_status=response.status_code,
            failed_routing_step=get_failed_routing_step(error_body),
            raw_response=error_body,
        )

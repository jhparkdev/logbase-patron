"""OpenRouter를 부르는 유일한 곳.

call_model은 실패해도 예외를 던지지 않고 실패 결과(CallResult)를 돌려준다.
조회 함수(list_models 등)도 오류 유형이 담긴 LookupResult를 돌려준다.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx

from app.openrouter.cancellation import run_unless_cancelled
from app.openrouter.errors import (
    USER_MESSAGES,
    ErrorType,
    classify_http_error,
    get_failed_routing_step,
)
from app.openrouter.failures import build_cancelled_result, build_failure_result
from app.openrouter.json_access import get_str
from app.openrouter.lookup_parsing import (
    parse_generation,
    parse_key_usage,
    parse_keys,
    parse_models,
)
from app.openrouter.lookup_result import (
    GenerationInfo,
    KeyInfo,
    KeyUsage,
    LookupResult,
    ModelInfo,
)
from app.openrouter.parsing import (
    build_result_from_chat_body,
    generation_id_from_headers,
    loads_decimal,
)
from app.openrouter.request import build_request_body
from app.openrouter.result import CallResult, CallStatus
from app.openrouter.streaming import (
    DONE_PAYLOAD,
    GenerationIdCallback,
    GenerationIdTracker,
    StreamReply,
    find_stream_error,
    get_data_payload,
    merge_chunks,
    parse_chunk,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
CHAT_COMPLETIONS_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

# 비용이 없는 조회는 네트워크 오류일 때만 다시 보낸다.
# 횟수와 간격은 아직 정해지지 않아(U-08) 임시 값이다.
LOOKUP_MAX_ATTEMPTS = 3
LOOKUP_RETRY_DELAY_SECONDS = 0.5
LOOKUP_TIMEOUT_SECONDS = 10.0

MANAGEMENT_KEY_MISSING_MESSAGE = "Management Key가 설정되어 있지 않습니다."

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _read_json(response: httpx.Response) -> Any:
    """응답 본문을 JSON으로 읽는다. JSON이 아니면 None."""
    try:
        return loads_decimal(response.text)
    except ValueError:
        return None


async def _run[T](
    work: Coroutine[Any, Any, T], cancel: asyncio.Event | None
) -> T | None:
    """취소 신호가 있으면 신호와 겨루고, 없으면 그냥 기다린다. 취소되면 None."""
    if cancel is None:
        return await work
    return await run_unless_cancelled(work, cancel)


def _lookup_failure(
    error_type: ErrorType, http_status: int | None = None
) -> LookupResult[Any]:
    return LookupResult(
        error_type=error_type,
        error_message=USER_MESSAGES[error_type],
        http_status=http_status,
    )


def _convert[T](
    fetched: LookupResult[dict[str, Any]],
    parser: Callable[[dict[str, Any]], T | None],
) -> LookupResult[T]:
    """받아 온 JSON을 결과 모양으로 바꾼다. 실패는 그대로 넘기고, 구조가 틀리면 INVALID_RESPONSE다."""
    if fetched.data is None:
        return LookupResult(
            error_type=fetched.error_type,
            error_message=fetched.error_message,
            http_status=fetched.http_status,
        )
    parsed = parser(fetched.data)
    if parsed is None:
        return _lookup_failure(ErrorType.INVALID_RESPONSE, fetched.http_status)
    return LookupResult(data=parsed, http_status=fetched.http_status)


class OpenRouterClient:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        api_key: str,
        management_key: str | None = None,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key
        self._management_key = management_key
        self._clock = clock
        self._sleep = sleep

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
        stream: bool = False,
        on_generation_id: GenerationIdCallback | None = None,
    ) -> CallResult:
        """모델을 호출하고 결과를 돌려준다. 실패해도 예외를 던지지 않는다.

        cancel 신호가 켜지면 호출을 멈추고 CANCELLED 결과를 돌려준다.
        신호가 없으면(None) 취소하지 않는다.

        stream이 True이면 답을 조각으로 받는다. 이때 timeout_seconds는 한 번 읽는
        시간이 아니라 호출 전체의 제한 시간이다. on_generation_id는 스트리밍일 때만
        쓰이며, 호출 ID를 처음 알게 된 순간(응답 헤더 또는 첫 조각) 한 번 불린다.
        끝나기 전에 끊기거나 취소돼도 ID를 저장해 둘 수 있게 하기 위해서다.
        """
        started_at = self._clock()
        request_body = build_request_body(
            model_id=model_id,
            messages=messages,
            max_tokens=max_tokens,
            json_schema=json_schema,
            provider_order=provider_order,
            allow_fallbacks=allow_fallbacks,
            stream=stream,
        )

        if cancel is not None and cancel.is_set():
            # 이미 취소 신호가 켜져 있으면 요청을 보내지 않는다.
            result = self._cancelled(model_id, started_at)
        elif stream:
            result = await self._send_stream(
                request_body,
                model_id,
                timeout_seconds,
                cancel,
                on_generation_id,
                started_at,
            )
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

    async def list_models(self) -> LookupResult[list[ModelInfo]]:
        """모델 목록과 가격을 가져온다. 공개 엔드포인트라 Key를 보내지 않는다."""
        fetched = await self._get_json("/models", token=None)
        return _convert(fetched, parse_models)

    async def get_generation(self, generation_id: str) -> LookupResult[GenerationInfo]:
        """호출 하나의 실제 비용을 조회한다. 비용 대조에 쓴다."""
        fetched = await self._get_json(
            "/generation", token=self._api_key, params={"id": generation_id}
        )
        if fetched.http_status == HTTPStatus.NOT_FOUND:
            # 404는 오류가 아니라 "아직 없거나 없는 호출"이다.
            # 시간을 두고 다시 조회할지는 대조 작업이 정한다.
            return LookupResult(
                data=GenerationInfo(found=False), http_status=fetched.http_status
            )
        return _convert(fetched, parse_generation)

    async def get_key_usage(self) -> LookupResult[KeyUsage]:
        """호출에 쓰는 Key의 사용량과 한도를 조회한다."""
        fetched = await self._get_json("/key", token=self._api_key)
        return _convert(fetched, parse_key_usage)

    async def list_keys(self, workspace_id: str) -> LookupResult[list[KeyInfo]]:
        """workspace의 Key 목록을 조회한다. Management Key가 필요하다."""
        if self._management_key is None:
            return LookupResult(
                error_type=ErrorType.AUTH_ERROR,
                error_message=MANAGEMENT_KEY_MISSING_MESSAGE,
            )
        fetched = await self._get_json(
            "/keys",
            token=self._management_key,
            params={"workspace_id": workspace_id},
        )
        return _convert(fetched, parse_keys)

    async def _get_json(
        self,
        path: str,
        *,
        token: str | None,
        params: dict[str, str] | None = None,
    ) -> LookupResult[dict[str, Any]]:
        """GET 조회를 보낸다. 네트워크 오류일 때만 다시 보낸다."""
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._http_client.get(
                    f"{OPENROUTER_BASE_URL}{path}",
                    params=params,
                    headers=headers,
                    timeout=LOOKUP_TIMEOUT_SECONDS,
                )
                break
            except httpx.RequestError as error:
                if attempt >= LOOKUP_MAX_ATTEMPTS:
                    error_type = (
                        ErrorType.TIMEOUT_ERROR
                        if isinstance(error, httpx.TimeoutException)
                        else ErrorType.NETWORK_ERROR
                    )
                    return self._finish_lookup(path, _lookup_failure(error_type))
                await self._sleep(LOOKUP_RETRY_DELAY_SECONDS)

        body = _read_json(response)
        if not response.is_success:
            error_body = body if isinstance(body, dict) else None
            error_type = classify_http_error(response.status_code, error_body)
            result = _lookup_failure(error_type, response.status_code)
        elif isinstance(body, dict):
            result = LookupResult(data=body, http_status=response.status_code)
        else:
            result = _lookup_failure(ErrorType.INVALID_RESPONSE, response.status_code)
        return self._finish_lookup(path, result)

    def _finish_lookup(
        self, path: str, result: LookupResult[dict[str, Any]]
    ) -> LookupResult[dict[str, Any]]:
        # 로그에는 경로와 결과만 남긴다. Key와 조회 값은 쓰지 않는다.
        logger.info(
            "openrouter lookup path=%s ok=%s http_status=%s",
            path,
            result.ok,
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
        return self._result_from_body(
            response.status_code,
            _read_json(response),
            generation_id_from_headers(response.headers),
            model_id,
            started_at,
        )

    async def _send_stream(
        self,
        request_body: dict[str, Any],
        model_id: str,
        timeout_seconds: float,
        cancel: asyncio.Event | None,
        on_generation_id: GenerationIdCallback | None,
        started_at: datetime,
    ) -> CallResult:
        # 스트리밍도 비용이 드는 호출이라 자동으로 다시 보내지 않는다.
        # 끊기거나 취소돼도 이미 알게 된 호출 ID는 결과에 남겨 비용 대조에 쓴다.
        tracker = GenerationIdTracker(on_generation_id)
        work = self._read_stream(request_body, timeout_seconds, tracker)
        try:
            reply = await _run(work, cancel)
        except httpx.TimeoutException, TimeoutError:
            return self._failure(
                CallStatus.TIMEOUT,
                ErrorType.TIMEOUT_ERROR,
                model_id,
                started_at,
                tracker.generation_id,
            )
        except httpx.RequestError:
            return self._failure(
                CallStatus.FAILED,
                ErrorType.NETWORK_ERROR,
                model_id,
                started_at,
                tracker.generation_id,
            )

        if reply is None:
            return self._cancelled(model_id, started_at, tracker.generation_id)

        if reply.midstream_error:
            # 스트림 도중의 오류는 모델을 제공하는 업체 쪽 오류로 본다.
            return build_failure_result(
                status=CallStatus.FAILED,
                error_type=ErrorType.PROVIDER_ERROR,
                requested_model=model_id,
                started_at=started_at,
                finished_at=self._clock(),
                http_status=reply.status_code,
                raw_response=reply.body,
                generation_id=tracker.generation_id,
            )
        return self._result_from_body(
            reply.status_code, reply.body, tracker.generation_id, model_id, started_at
        )

    async def _read_stream(
        self,
        request_body: dict[str, Any],
        timeout_seconds: float,
        tracker: GenerationIdTracker,
    ) -> StreamReply:
        """스트리밍 요청을 보내고 끝까지 읽는다. 호출 ID를 알게 되면 바로 tracker에 알린다."""
        # httpx의 timeout은 한 번 읽는 시간만 제한한다. 호출 전체 시간은 따로 제한한다.
        async with (
            asyncio.timeout(timeout_seconds),
            self._http_client.stream(
                "POST",
                CHAT_COMPLETIONS_URL,
                json=request_body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=timeout_seconds,
            ) as response,
        ):
            await tracker.note(generation_id_from_headers(response.headers))

            if not response.is_success:
                # 오류 응답은 조각이 아니라 일반 JSON이다.
                await response.aread()
                return StreamReply(response.status_code, _read_json(response))

            chunks: list[dict[str, Any]] = []
            async for line in response.aiter_lines():
                payload = get_data_payload(line)
                if payload is None:
                    continue
                if payload == DONE_PAYLOAD:
                    break
                chunk = parse_chunk(payload)
                if chunk is None:
                    return StreamReply(response.status_code, None)
                await tracker.note(get_str(chunk, "id"))
                chunks.append(chunk)

            error = find_stream_error(chunks)
            if error is not None:
                return StreamReply(
                    response.status_code, {"error": error}, midstream_error=True
                )
            return StreamReply(response.status_code, merge_chunks(chunks))

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
        return await _run(work, cancel)

    def _cancelled(
        self, model_id: str, started_at: datetime, generation_id: str | None = None
    ) -> CallResult:
        return build_cancelled_result(
            requested_model=model_id,
            started_at=started_at,
            finished_at=self._clock(),
            generation_id=generation_id,
        )

    def _failure(
        self,
        status: CallStatus,
        error_type: ErrorType,
        model_id: str,
        started_at: datetime,
        generation_id: str | None = None,
    ) -> CallResult:
        return build_failure_result(
            status=status,
            error_type=error_type,
            requested_model=model_id,
            started_at=started_at,
            finished_at=self._clock(),
            generation_id=generation_id,
        )

    def _result_from_body(
        self,
        status_code: int,
        body: Any,
        generation_id: str | None,
        model_id: str,
        started_at: datetime,
    ) -> CallResult:
        """받은 응답(일반 응답이든 합친 스트림이든)을 CallResult로 바꾼다.

        generation_id는 응답 헤더나 조각에서 알게 된 호출 ID다. 본문에 id가 없을 때 쓴다.
        """
        finished_at = self._clock()

        if httpx.codes.is_success(status_code):
            if not isinstance(body, dict):
                return build_failure_result(
                    status=CallStatus.FAILED,
                    error_type=ErrorType.INVALID_RESPONSE,
                    requested_model=model_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    http_status=status_code,
                    generation_id=generation_id,
                )
            return build_result_from_chat_body(
                body,
                requested_model=model_id,
                started_at=started_at,
                finished_at=finished_at,
                http_status=status_code,
                generation_id_header=generation_id,
            )

        error_body = body if isinstance(body, dict) else None
        return build_failure_result(
            status=CallStatus.FAILED,
            error_type=classify_http_error(status_code, error_body),
            requested_model=model_id,
            started_at=started_at,
            finished_at=finished_at,
            http_status=status_code,
            failed_routing_step=get_failed_routing_step(error_body),
            raw_response=error_body,
            generation_id=generation_id,
        )

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.openrouter.client import CHAT_COMPLETIONS_URL, OpenRouterClient
from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.failures import CANCELLED_MESSAGE
from app.openrouter.result import CallResult, CallStatus, CostStatus

FAKE_API_KEY = "sk-or-v1-fake-key-for-tests"
SECRET_PROMPT = "이것은 로그에 남으면 안 되는 프롬프트입니다"
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000001")
MODEL_ID = "mistralai/mistral-nemo"
STARTED_AT = datetime(2026, 10, 27, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 10, 27, 1, 0, 1, 500000, tzinfo=UTC)

SUCCESS_BODY_TEXT = json.dumps(
    {
        "id": "gen-abc123",
        "model": MODEL_ID,
        "provider": "DekaLLM",
        "choices": [{"message": {"role": "assistant", "content": "2"}}],
        "usage": {"prompt_tokens": 16, "completion_tokens": 2, "cost": 3.48e-07},
    }
)

HANG_SECONDS = 3600

Handler = Callable[[httpx.Request], httpx.Response]
AsyncHandler = Callable[[httpx.Request], Awaitable[httpx.Response]]
ClientFactory = Callable[[Handler | AsyncHandler], OpenRouterClient]


@pytest.fixture
async def make_client() -> AsyncIterator[ClientFactory]:
    """가짜 서버(MockTransport)에 연결된 OpenRouterClient를 만들어 주는 함수."""
    http_clients: list[httpx.AsyncClient] = []

    def factory(handler: Handler | AsyncHandler) -> OpenRouterClient:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        http_clients.append(http_client)
        times = iter([STARTED_AT, FINISHED_AT])
        return OpenRouterClient(
            http_client=http_client,
            api_key=FAKE_API_KEY,
            clock=lambda: next(times),
        )

    yield factory

    for http_client in http_clients:
        await http_client.aclose()


async def call(client: OpenRouterClient, **overrides: Any) -> CallResult:
    arguments: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "model_id": MODEL_ID,
        "messages": [{"role": "user", "content": SECRET_PROMPT}],
        "max_tokens": 100,
        "timeout_seconds": 60.0,
    }
    arguments.update(overrides)
    return await client.call_model(**arguments)


def respond_success(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=SUCCESS_BODY_TEXT)


def respond_500(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, text="Internal Server Error")


def raise_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


def raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection failed", request=request)


# ---------------------------------------------------------------
# 정상 호출
# ---------------------------------------------------------------
async def test_정상_응답은_SUCCESS와_CONFIRMED로_돌려준다(
    make_client: ClientFactory,
) -> None:
    client = make_client(respond_success)

    result = await call(client)

    assert result.status == CallStatus.SUCCESS
    assert result.error_type is None
    assert result.content == "2"
    assert result.requested_model == MODEL_ID
    assert result.provider == "DekaLLM"
    assert result.generation_id == "gen-abc123"
    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("3.48e-07")
    assert result.latency_ms == 1500


async def test_요청은_정해진_주소로_Key와_함께_POST로_보낸다(
    make_client: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_success(request)

    await call(make_client(handler))

    request = captured[0]
    assert request.method == "POST"
    assert str(request.url) == CHAT_COMPLETIONS_URL
    assert request.headers["Authorization"] == f"Bearer {FAKE_API_KEY}"
    body = json.loads(request.content)
    assert body["model"] == MODEL_ID
    assert body["messages"] == [{"role": "user", "content": SECRET_PROMPT}]
    assert body["max_tokens"] == 100
    assert body["provider"] == {"allow_fallbacks": False}


async def test_모든_호출에_timeout을_명시한다(make_client: ClientFactory) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_success(request)

    await call(make_client(handler), timeout_seconds=30.0)

    expected = {"connect": 30.0, "read": 30.0, "write": 30.0, "pool": 30.0}
    assert captured[0].extensions["timeout"] == expected


async def test_업체_고정과_JSON_Schema를_요청에_담아_보낸다(
    make_client: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_success(request)

    await call(
        make_client(handler),
        provider_order=["DeepInfra"],
        json_schema={"type": "object"},
    )

    body = json.loads(captured[0].content)
    assert body["provider"]["order"] == ["DeepInfra"]
    assert body["provider"]["require_parameters"] is True
    assert body["response_format"]["type"] == "json_schema"


# ---------------------------------------------------------------
# HTTP 오류 응답: 예외를 던지지 않고 실패 결과로 돌려준다
# ---------------------------------------------------------------
def routing_error_body(step: str) -> dict[str, Any]:
    return {"error": {"code": 404, "metadata": {"failed_routing_step": step}}}


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (401, {"error": {"code": 401, "message": "no auth"}}, ErrorType.AUTH_ERROR),
        (429, {"error": {"code": 429, "message": "slow"}}, ErrorType.RATE_LIMIT),
        (500, {"error": {"code": 500, "message": "boom"}}, ErrorType.PROVIDER_ERROR),
        (
            404,
            routing_error_body("Filter by Fallback"),
            ErrorType.PROVIDER_ERROR,
        ),
        (
            404,
            routing_error_body("Filter by Image Support"),
            ErrorType.UNSUPPORTED_INPUT,
        ),
        (
            404,
            routing_error_body("Filter by Parameters"),
            ErrorType.UNSUPPORTED_INPUT,
        ),
    ],
)
async def test_HTTP_오류는_오류_유형을_정해_실패_결과로_돌려준다(
    make_client: ClientFactory,
    status_code: int,
    body: dict[str, Any],
    expected: ErrorType,
) -> None:
    client = make_client(lambda request: httpx.Response(status_code, json=body))

    result = await call(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == expected
    assert result.error_message == USER_MESSAGES[expected]
    assert result.http_status == status_code
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.raw_response == body


async def test_404이면_라우팅_실패_단계를_함께_돌려준다(
    make_client: ClientFactory,
) -> None:
    body = routing_error_body("Filter by Fallback")
    client = make_client(lambda request: httpx.Response(404, json=body))

    result = await call(client)

    assert result.failed_routing_step == "Filter by Fallback"


async def test_오류_본문이_JSON이_아니어도_실패_결과로_돌려준다(
    make_client: ClientFactory,
) -> None:
    client = make_client(respond_500)

    result = await call(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.http_status == 500
    assert result.raw_response is None


# ---------------------------------------------------------------
# 200인데 내용이 이상한 경우
# ---------------------------------------------------------------
@pytest.mark.parametrize("text", ["이것은 JSON이 아니다", "[1, 2]", ""])
async def test_200인데_JSON_객체가_아니면_INVALID_RESPONSE다(
    make_client: ClientFactory, text: str
) -> None:
    client = make_client(lambda request: httpx.Response(200, text=text))

    result = await call(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.http_status == 200
    assert result.cost_status == CostStatus.UNKNOWN


async def test_200인데_본문이_비어_있으면_INVALID_RESPONSE이고_ID는_남긴다(
    make_client: ClientFactory,
) -> None:
    body = json.loads(SUCCESS_BODY_TEXT)
    body["choices"][0]["message"]["content"] = ""
    client = make_client(lambda request: httpx.Response(200, json=body))

    result = await call(client)

    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.generation_id == "gen-abc123"


# ---------------------------------------------------------------
# 시간 초과와 네트워크 오류
# ---------------------------------------------------------------
async def test_시간이_초과되면_TIMEOUT_결과로_돌려준다(
    make_client: ClientFactory,
) -> None:
    client = make_client(raise_timeout)

    result = await call(client)

    assert result.status == CallStatus.TIMEOUT
    assert result.error_type == ErrorType.TIMEOUT_ERROR
    assert result.http_status is None
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.latency_ms == 1500


async def test_연결에_실패하면_NETWORK_ERROR_결과로_돌려준다(
    make_client: ClientFactory,
) -> None:
    client = make_client(raise_connect_error)

    result = await call(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.NETWORK_ERROR
    assert result.http_status is None
    assert result.cost_status == CostStatus.UNKNOWN


# ---------------------------------------------------------------
# 비용이 드는 호출은 실패해도 자동으로 다시 보내지 않는다
# ---------------------------------------------------------------
@pytest.mark.parametrize("behavior", [respond_500, raise_timeout, raise_connect_error])
async def test_실패해도_자동으로_다시_보내지_않는다(
    make_client: ClientFactory,
    behavior: Handler,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return behavior(request)

    await call(make_client(handler))

    assert call_count == 1


# ---------------------------------------------------------------
# Key와 Prompt는 결과나 로그에 남기지 않는다
# ---------------------------------------------------------------
async def test_실패_결과와_로그에_Key와_프롬프트가_남지_않는다(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        message = f"cannot reach server with {FAKE_API_KEY}"
        raise httpx.ConnectError(message, request=request)

    caplog.set_level(logging.DEBUG)

    result = await call(make_client(handler))

    assert FAKE_API_KEY not in result.model_dump_json()
    assert FAKE_API_KEY not in caplog.text
    assert SECRET_PROMPT not in caplog.text


async def test_로그에는_request_id와_결과_상태만_남긴다(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    await call(make_client(respond_success))

    assert str(REQUEST_ID) in caplog.text
    assert "SUCCESS" in caplog.text
    assert SECRET_PROMPT not in caplog.text
    assert FAKE_API_KEY not in caplog.text


# ---------------------------------------------------------------
# 취소
# ---------------------------------------------------------------
class HangingServer:
    """응답을 주지 않고 기다리는 가짜 서버. 연결이 끊기면 그 사실을 기록한다."""

    def __init__(self) -> None:
        self.request_received = asyncio.Event()
        self.was_cancelled = False
        self.call_count = 0

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        self.request_received.set()
        try:
            await asyncio.sleep(HANG_SECONDS)
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise
        return respond_success(request)


async def test_보내기_전에_취소_신호가_켜져_있으면_요청을_보내지_않는다(
    make_client: ClientFactory,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return respond_success(request)

    cancel = asyncio.Event()
    cancel.set()

    result = await call(make_client(handler), cancel=cancel)

    assert call_count == 0
    assert result.status == CallStatus.CANCELLED
    assert result.error_type is None
    assert result.error_message == CANCELLED_MESSAGE
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.http_status is None


async def test_응답을_기다리는_중_취소하면_연결을_끊고_CANCELLED로_돌려준다(
    make_client: ClientFactory,
) -> None:
    server = HangingServer()
    cancel = asyncio.Event()
    client = make_client(server.handler)

    task = asyncio.create_task(call(client, cancel=cancel))
    await server.request_received.wait()
    cancel.set()
    result = await task

    assert result.status == CallStatus.CANCELLED
    assert result.error_type is None
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.latency_ms == 1500
    assert server.was_cancelled is True
    assert server.call_count == 1


async def test_취소_신호가_켜진_순간에_응답이_도착했으면_받은_결과를_돌려준다(
    make_client: ClientFactory,
) -> None:
    cancel = asyncio.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        cancel.set()
        return respond_success(request)

    result = await call(make_client(handler), cancel=cancel)

    assert result.status == CallStatus.SUCCESS
    assert result.cost_status == CostStatus.CONFIRMED


@pytest.mark.parametrize("use_cancel_signal", [False, True])
async def test_바깥에서_작업이_취소되면_CancelledError를_삼키지_않는다(
    make_client: ClientFactory, use_cancel_signal: bool
) -> None:
    server = HangingServer()
    client = make_client(server.handler)
    cancel = asyncio.Event() if use_cancel_signal else None

    task = asyncio.create_task(call(client, cancel=cancel))
    await server.request_received.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert server.was_cancelled is True


async def test_취소되어도_로그에는_상태만_남는다(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    cancel = asyncio.Event()
    cancel.set()
    caplog.set_level(logging.INFO)

    await call(make_client(respond_success), cancel=cancel)

    assert str(REQUEST_ID) in caplog.text
    assert "CANCELLED" in caplog.text
    assert SECRET_PROMPT not in caplog.text
    assert FAKE_API_KEY not in caplog.text


# ---------------------------------------------------------------
# 호출 ID는 응답 헤더에서도 받는다
# ---------------------------------------------------------------
ID_HEADERS = {"X-Generation-Id": "gen-from-header"}


async def test_오류_응답의_헤더에_호출_ID가_있으면_결과에_담는다(
    make_client: ClientFactory,
) -> None:
    client = make_client(
        lambda request: httpx.Response(500, text="boom", headers=ID_HEADERS)
    )

    result = await call(client)

    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.generation_id == "gen-from-header"


async def test_JSON이_아닌_200_응답도_헤더의_호출_ID를_담는다(
    make_client: ClientFactory,
) -> None:
    client = make_client(
        lambda request: httpx.Response(200, text="not json", headers=ID_HEADERS)
    )

    result = await call(client)

    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.generation_id == "gen-from-header"


async def test_본문에_ID가_없는_정상_응답은_헤더의_호출_ID를_쓴다(
    make_client: ClientFactory,
) -> None:
    body = json.loads(SUCCESS_BODY_TEXT)
    del body["id"]
    client = make_client(
        lambda request: httpx.Response(200, json=body, headers=ID_HEADERS)
    )

    result = await call(client)

    assert result.status == CallStatus.SUCCESS
    assert result.generation_id == "gen-from-header"


async def test_정상_응답은_본문과_헤더가_다르면_본문의_호출_ID를_쓴다(
    make_client: ClientFactory,
) -> None:
    client = make_client(
        lambda request: httpx.Response(200, text=SUCCESS_BODY_TEXT, headers=ID_HEADERS)
    )

    result = await call(client)

    assert result.generation_id == "gen-abc123"


async def test_헤더가_없는_오류_응답의_호출_ID는_None이다(
    make_client: ClientFactory,
) -> None:
    result = await call(make_client(respond_500))

    assert result.generation_id is None

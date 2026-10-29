import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.openrouter.client import OpenRouterClient
from app.openrouter.errors import ErrorType
from app.openrouter.failures import CANCELLED_MESSAGE
from app.openrouter.result import CallResult, CallStatus, CostStatus

FAKE_API_KEY = "sk-or-v1-fake-key-for-tests"
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000001")
MODEL_ID = "mistralai/mistral-nemo"
STARTED_AT = datetime(2026, 10, 28, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 10, 28, 1, 0, 1, 500000, tzinfo=UTC)

HANG_SECONDS = 3600
ID_HEADERS = {"X-Generation-Id": "gen-from-header"}

TEXT_CHUNKS: list[dict[str, Any]] = [
    {
        "id": "gen-stream1",
        "model": MODEL_ID,
        "provider": "DekaLLM",
        "choices": [{"delta": {"role": "assistant", "content": "안"}}],
    },
    {
        "id": "gen-stream1",
        "model": MODEL_ID,
        "provider": "DekaLLM",
        "choices": [{"delta": {"content": "녕"}, "finish_reason": "stop"}],
    },
]
USAGE_CHUNK: dict[str, Any] = {
    "id": "gen-stream1",
    "model": MODEL_ID,
    "provider": "DekaLLM",
    "choices": [],
    "usage": {
        "prompt_tokens": 16,
        "completion_tokens": 2,
        "total_tokens": 18,
        "cost": 3.48e-07,
    },
}
SUCCESS_CHUNKS = [*TEXT_CHUNKS, USAGE_CHUNK]

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


async def call_stream(client: OpenRouterClient, **overrides: Any) -> CallResult:
    arguments: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "model_id": MODEL_ID,
        "messages": [{"role": "user", "content": "안녕"}],
        "max_tokens": 100,
        "timeout_seconds": 60.0,
        "stream": True,
    }
    arguments.update(overrides)
    return await client.call_model(**arguments)


def sse_line(event: dict[str, Any] | str) -> str:
    payload = event if isinstance(event, str) else json.dumps(event)
    return f"data: {payload}\n\n"


def sse_text(events: list[dict[str, Any] | str], *, done: bool = True) -> str:
    lines = [sse_line(event) for event in events]
    if done:
        lines.append(sse_line("[DONE]"))
    return "".join(lines)


def stream_response(
    events: list[dict[str, Any] | str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    text = sse_text(SUCCESS_CHUNKS if events is None else events)
    all_headers = {"content-type": "text/event-stream", **(headers or {})}
    return httpx.Response(200, text=text, headers=all_headers)


def respond_stream(request: httpx.Request) -> httpx.Response:
    return stream_response()


class IdRecorder:
    def __init__(self) -> None:
        self.received: list[str] = []

    async def __call__(self, generation_id: str) -> None:
        self.received.append(generation_id)


class HangingStream:
    """첫 조각을 보낸 뒤 멈추는 가짜 스트림. 연결이 끊기면 그 사실을 기록한다."""

    def __init__(self) -> None:
        self.first_chunk_read = asyncio.Event()
        self.was_cancelled = False

    async def body(self) -> AsyncIterator[bytes]:
        yield sse_line(TEXT_CHUNKS[0]).encode()
        # 받는 쪽이 다음 조각을 달라고 할 때 여기로 돌아온다.
        self.first_chunk_read.set()
        try:
            await asyncio.sleep(HANG_SECONDS)
        except asyncio.CancelledError:
            self.was_cancelled = True
            raise

    def handler(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers=ID_HEADERS, content=self.body())


# ---------------------------------------------------------------
# 요청
# ---------------------------------------------------------------
async def test_스트리밍이면_stream을_true로_보낸다(make_client: ClientFactory) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_stream(request)

    await call_stream(make_client(handler))

    assert json.loads(captured[0].content)["stream"] is True


async def test_스트리밍을_켜지_않으면_stream을_보내지_않는다(
    make_client: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "id": "gen-abc",
                "model": MODEL_ID,
                "choices": [{"message": {"content": "2"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    await call_stream(make_client(handler), stream=False)

    assert "stream" not in json.loads(captured[0].content)


# ---------------------------------------------------------------
# 정상 스트림
# ---------------------------------------------------------------
async def test_조각을_이어_붙여_SUCCESS_결과로_돌려준다(
    make_client: ClientFactory,
) -> None:
    result = await call_stream(make_client(respond_stream))

    assert result.status == CallStatus.SUCCESS
    assert result.error_type is None
    assert result.content == "안녕"
    assert result.finish_reason == "stop"
    assert result.requested_model == MODEL_ID
    assert result.actual_model == MODEL_ID
    assert result.provider == "DekaLLM"
    assert result.generation_id == "gen-stream1"
    assert result.prompt_tokens == 16
    assert result.completion_tokens == 2
    assert result.total_tokens == 18
    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("3.48e-07")
    assert result.latency_ms == 1500


async def test_주석_줄과_빈_줄은_무시한다(make_client: ClientFactory) -> None:
    text = ": OPENROUTER PROCESSING\n\n" + sse_text(SUCCESS_CHUNKS)
    client = make_client(lambda request: httpx.Response(200, text=text))

    result = await call_stream(client)

    assert result.status == CallStatus.SUCCESS
    assert result.content == "안녕"


async def test_사용량에_비용이_없으면_비용_미확인이다(
    make_client: ClientFactory,
) -> None:
    usage_without_cost = {
        **USAGE_CHUNK,
        "usage": {"prompt_tokens": 16, "completion_tokens": 2},
    }
    client = make_client(
        lambda request: stream_response([*TEXT_CHUNKS, usage_without_cost])
    )

    result = await call_stream(client)

    assert result.status == CallStatus.SUCCESS
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None


# ---------------------------------------------------------------
# 이상한 스트림
# ---------------------------------------------------------------
async def test_사용량_조각이_없으면_INVALID_RESPONSE이고_ID는_남긴다(
    make_client: ClientFactory,
) -> None:
    client = make_client(lambda request: stream_response(TEXT_CHUNKS))

    result = await call_stream(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.generation_id == "gen-stream1"


async def test_깨진_조각이_있으면_INVALID_RESPONSE이고_헤더의_ID는_남긴다(
    make_client: ClientFactory,
) -> None:
    client = make_client(
        lambda request: stream_response(["{not json"], headers=ID_HEADERS)
    )

    result = await call_stream(client)

    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.generation_id == "gen-from-header"


async def test_스트림_중간에_오류가_오면_PROVIDER_ERROR로_돌려준다(
    make_client: ClientFactory,
) -> None:
    error_chunk = {
        "id": "gen-stream1",
        "error": {"code": 502, "message": "provider disconnected"},
        "choices": [{"delta": {"content": ""}, "finish_reason": "error"}],
    }
    client = make_client(lambda request: stream_response([TEXT_CHUNKS[0], error_chunk]))

    result = await call_stream(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.http_status == 200
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.generation_id == "gen-stream1"


async def test_연결이_중간에_끊기면_NETWORK_ERROR이고_ID는_남긴다(
    make_client: ClientFactory,
) -> None:
    async def broken_body() -> AsyncIterator[bytes]:
        yield sse_line(TEXT_CHUNKS[0]).encode()
        message = "connection lost"
        raise httpx.ReadError(message)

    client = make_client(
        lambda request: httpx.Response(200, headers=ID_HEADERS, content=broken_body())
    )

    result = await call_stream(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.NETWORK_ERROR
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.generation_id == "gen-from-header"


# ---------------------------------------------------------------
# HTTP 오류 응답은 일반 호출과 똑같이 분류한다
# ---------------------------------------------------------------
async def test_스트리밍_요청의_HTTP_오류도_오류_유형으로_분류한다(
    make_client: ClientFactory,
) -> None:
    body = {
        "error": {
            "code": 404,
            "metadata": {"failed_routing_step": "Filter by Parameters"},
        }
    }
    client = make_client(lambda request: httpx.Response(404, json=body))

    result = await call_stream(client)

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.UNSUPPORTED_INPUT
    assert result.http_status == 404
    assert result.failed_routing_step == "Filter by Parameters"
    assert result.raw_response == body


async def test_스트리밍_요청의_오류_응답도_헤더의_호출_ID를_담는다(
    make_client: ClientFactory,
) -> None:
    client = make_client(
        lambda request: httpx.Response(500, text="boom", headers=ID_HEADERS)
    )

    result = await call_stream(client)

    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.generation_id == "gen-from-header"


@pytest.mark.parametrize("failing", [True, False])
async def test_스트리밍도_실패하면_자동으로_다시_보내지_않는다(
    make_client: ClientFactory, failing: bool
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if failing:
            return httpx.Response(500, text="boom")
        return respond_stream(request)

    await call_stream(make_client(handler))

    assert call_count == 1


# ---------------------------------------------------------------
# 호출 ID는 스트림을 다 읽기 전에 알려 준다
# ---------------------------------------------------------------
async def test_본문을_읽기_전에_헤더의_호출_ID를_콜백에_알린다(
    make_client: ClientFactory,
) -> None:
    events: list[str] = []

    async def on_generation_id(generation_id: str) -> None:
        events.append(f"id:{generation_id}")

    async def body() -> AsyncIterator[bytes]:
        events.append("본문 읽기 시작")
        yield sse_text(SUCCESS_CHUNKS).encode()

    client = make_client(
        lambda request: httpx.Response(200, headers=ID_HEADERS, content=body())
    )

    result = await call_stream(client, on_generation_id=on_generation_id)

    assert events == ["id:gen-from-header", "본문 읽기 시작"]
    assert result.status == CallStatus.SUCCESS


@pytest.mark.parametrize("headers", [None, {"X-Generation-Id": "bad id"}])
async def test_헤더에_쓸_만한_ID가_없으면_첫_조각의_ID를_알린다(
    make_client: ClientFactory, headers: dict[str, str] | None
) -> None:
    recorder = IdRecorder()
    client = make_client(lambda request: stream_response(headers=headers))

    await call_stream(client, on_generation_id=recorder)

    assert recorder.received == ["gen-stream1"]


async def test_콜백이_실패해도_호출은_성공한다(make_client: ClientFactory) -> None:
    async def failing_callback(generation_id: str) -> None:
        message = "저장 실패"
        raise RuntimeError(message)

    result = await call_stream(
        make_client(respond_stream), on_generation_id=failing_callback
    )

    assert result.status == CallStatus.SUCCESS
    assert result.content == "안녕"


# ---------------------------------------------------------------
# 취소와 시간 초과
# ---------------------------------------------------------------
async def test_보내기_전에_취소_신호가_켜져_있으면_요청을_보내지_않는다(
    make_client: ClientFactory,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return respond_stream(request)

    cancel = asyncio.Event()
    cancel.set()

    result = await call_stream(make_client(handler), cancel=cancel)

    assert call_count == 0
    assert result.status == CallStatus.CANCELLED
    assert result.error_message == CANCELLED_MESSAGE


async def test_스트림을_읽는_중_취소하면_연결을_끊고_알게_된_ID를_남긴다(
    make_client: ClientFactory,
) -> None:
    server = HangingStream()
    cancel = asyncio.Event()
    client = make_client(server.handler)

    task = asyncio.create_task(call_stream(client, cancel=cancel))
    await server.first_chunk_read.wait()
    cancel.set()
    result = await task

    assert result.status == CallStatus.CANCELLED
    assert result.error_type is None
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.generation_id == "gen-from-header"
    assert server.was_cancelled is True


async def test_스트림이_멈추면_전체_시간_제한으로_TIMEOUT이고_ID는_남긴다(
    make_client: ClientFactory,
) -> None:
    server = HangingStream()
    client = make_client(server.handler)

    result = await call_stream(client, timeout_seconds=0.05)

    assert result.status == CallStatus.TIMEOUT
    assert result.error_type == ErrorType.TIMEOUT_ERROR
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.generation_id == "gen-from-header"
    assert server.was_cancelled is True


async def test_바깥에서_작업이_취소되면_스트리밍도_CancelledError를_삼키지_않는다(
    make_client: ClientFactory,
) -> None:
    server = HangingStream()
    client = make_client(server.handler)

    task = asyncio.create_task(call_stream(client))
    await server.first_chunk_read.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert server.was_cancelled is True

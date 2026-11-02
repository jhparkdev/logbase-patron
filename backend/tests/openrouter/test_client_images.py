import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.openrouter.client import IMAGES_URL, OpenRouterClient
from app.openrouter.errors import ErrorType
from app.openrouter.image_result import ImageCallResult
from app.openrouter.result import CallStatus, CostStatus

FAKE_API_KEY = "sk-or-v1-fake-key-for-tests"
SECRET_PROMPT = "이것은 로그에 남으면 안 되는 이미지 프롬프트입니다"
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000002")
MODEL_ID = "bytedance-seed/seedream-4.5"
STARTED_AT = datetime(2026, 11, 2, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 11, 2, 1, 0, 8, tzinfo=UTC)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x01" * 64
PNG_B64 = base64.b64encode(PNG_BYTES).decode()

SUCCESS_BODY_TEXT = json.dumps(
    {
        "created": 1793581200,
        "data": [{"b64_json": PNG_B64, "media_type": "image/png"}],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 4096,
            "total_tokens": 4108,
            "cost": 0.04,
        },
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


async def generate(client: OpenRouterClient, **overrides: Any) -> ImageCallResult:
    arguments: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "model_id": MODEL_ID,
        "prompt": SECRET_PROMPT,
        "timeout_seconds": 120.0,
    }
    arguments.update(overrides)
    return await client.generate_image(**arguments)


def respond_success(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=SUCCESS_BODY_TEXT)


# ---------------------------------------------------------------
# 정상 호출
# ---------------------------------------------------------------
async def test_정상_응답은_이미지와_확정_비용을_돌려준다(
    make_client: ClientFactory,
) -> None:
    result = await generate(make_client(respond_success))

    assert result.status == CallStatus.SUCCESS
    assert [image.data for image in result.images] == [PNG_BYTES]
    assert result.cost_status == CostStatus.CONFIRMED
    assert result.cost_usd == Decimal("0.04")
    assert result.latency_ms == 8000


async def test_요청은_이미지_주소로_Key와_함께_POST로_보낸다(
    make_client: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_success(request)

    await generate(make_client(handler))

    request = captured[0]
    assert request.method == "POST"
    assert str(request.url) == IMAGES_URL
    assert request.headers["Authorization"] == f"Bearer {FAKE_API_KEY}"
    body = json.loads(request.content)
    assert body == {
        "model": MODEL_ID,
        "prompt": SECRET_PROMPT,
        "provider": {"allow_fallbacks": False},
    }


async def test_참고_이미지와_생성_설정을_요청에_담는다(
    make_client: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_success(request)

    await generate(
        make_client(handler),
        input_image_urls=["data:image/png;base64,AAAA"],
        n=2,
        resolution="2K",
        aspect_ratio="1:1",
        quality="high",
        provider_order=["bytedance"],
    )

    body = json.loads(captured[0].content)
    assert body["input_references"] == [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    ]
    assert body["n"] == 2
    assert body["resolution"] == "2K"
    assert body["aspect_ratio"] == "1:1"
    assert body["quality"] == "high"
    assert body["provider"]["order"] == ["bytedance"]


async def test_모든_호출에_timeout을_명시한다(make_client: ClientFactory) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_success(request)

    await generate(make_client(handler), timeout_seconds=90.0)

    expected = {"connect": 90.0, "read": 90.0, "write": 90.0, "pool": 90.0}
    assert captured[0].extensions["timeout"] == expected


async def test_헤더에_호출_ID가_있으면_결과에_담는다(
    make_client: ClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=SUCCESS_BODY_TEXT, headers={"X-Generation-Id": "gen-img123"}
        )

    result = await generate(make_client(handler))

    assert result.generation_id == "gen-img123"


# ---------------------------------------------------------------
# 실패
# ---------------------------------------------------------------
async def test_502는_업체_오류_실패로_돌려준다(make_client: ClientFactory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502, json={"error": {"code": 502, "message": "upstream failed"}}
        )

    result = await generate(make_client(handler))

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.http_status == 502
    assert result.cost_status == CostStatus.UNKNOWN


async def test_200인데_JSON이_아니면_INVALID_RESPONSE다(
    make_client: ClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    result = await generate(make_client(handler))

    assert result.error_type == ErrorType.INVALID_RESPONSE


async def test_시간이_초과되면_TIMEOUT_결과로_돌려준다(
    make_client: ClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    result = await generate(make_client(handler))

    assert result.status == CallStatus.TIMEOUT
    assert result.error_type == ErrorType.TIMEOUT_ERROR
    assert result.cost_status == CostStatus.UNKNOWN


async def test_연결에_실패하면_NETWORK_ERROR_결과로_돌려준다(
    make_client: ClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    result = await generate(make_client(handler))

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.NETWORK_ERROR


async def test_실패해도_자동으로_다시_보내지_않는다(
    make_client: ClientFactory,
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, text="Internal Server Error")

    await generate(make_client(handler))

    assert len(calls) == 1


# ---------------------------------------------------------------
# 취소
# ---------------------------------------------------------------
async def test_보내기_전에_취소_신호가_켜져_있으면_요청을_보내지_않는다(
    make_client: ClientFactory,
) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return respond_success(request)

    cancel = asyncio.Event()
    cancel.set()
    result = await generate(make_client(handler), cancel=cancel)

    assert calls == []
    assert result.status == CallStatus.CANCELLED
    assert result.cost_status == CostStatus.UNKNOWN


async def test_응답을_기다리는_중_취소하면_CANCELLED로_돌려준다(
    make_client: ClientFactory,
) -> None:
    cancel = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        cancel.set()
        await asyncio.sleep(HANG_SECONDS)
        return respond_success(request)

    result = await generate(make_client(handler), cancel=cancel)

    assert result.status == CallStatus.CANCELLED


# ---------------------------------------------------------------
# 비밀정보
# ---------------------------------------------------------------
async def test_로그에는_request_id와_결과_상태만_남긴다(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.openrouter.client"):
        await generate(make_client(respond_success))

    assert str(REQUEST_ID) in caplog.text
    assert "SUCCESS" in caplog.text
    assert FAKE_API_KEY not in caplog.text
    assert SECRET_PROMPT not in caplog.text
    assert PNG_B64 not in caplog.text


async def test_실패_결과에_Key와_프롬프트가_남지_않는다(
    make_client: ClientFactory,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"code": 400, "message": "bad"}})

    result = await generate(make_client(handler))

    dumped = result.model_dump_json()
    assert FAKE_API_KEY not in dumped
    assert SECRET_PROMPT not in dumped

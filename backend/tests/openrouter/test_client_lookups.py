import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.openrouter.client import (
    LOOKUP_MAX_ATTEMPTS,
    LOOKUP_RETRY_DELAY_SECONDS,
    LOOKUP_TIMEOUT_SECONDS,
    OPENROUTER_BASE_URL,
    OpenRouterClient,
)
from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.lookup_result import LookupResult

FAKE_API_KEY = "sk-or-v1-fake-key-for-tests"
FAKE_MANAGEMENT_KEY = "sk-or-v1-fake-management-key"

Handler = Callable[[httpx.Request], httpx.Response]


class ClientFactory:
    """가짜 서버에 연결된 OpenRouterClient를 만들어 주는 도구."""

    def __init__(self) -> None:
        self.http_clients: list[httpx.AsyncClient] = []
        self.sleeps: list[float] = []

    def __call__(
        self, handler: Handler, *, management_key: str | None = FAKE_MANAGEMENT_KEY
    ) -> OpenRouterClient:
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.http_clients.append(http_client)

        async def fake_sleep(seconds: float) -> None:
            self.sleeps.append(seconds)

        return OpenRouterClient(
            http_client=http_client,
            api_key=FAKE_API_KEY,
            management_key=management_key,
            sleep=fake_sleep,
        )


@pytest.fixture
async def factory() -> AsyncIterator[ClientFactory]:
    client_factory = ClientFactory()
    yield client_factory
    for http_client in client_factory.http_clients:
        await http_client.aclose()


LookupCall = Callable[[OpenRouterClient], Awaitable[LookupResult[Any]]]

LOOKUP_CALLS: dict[str, LookupCall] = {
    "list_models": lambda client: client.list_models(),
    "get_model_endpoints": lambda client: client.get_model_endpoints("a/b"),
    "get_generation": lambda client: client.get_generation("gen-abc"),
    "get_key_usage": lambda client: client.get_key_usage(),
    "list_keys": lambda client: client.list_keys("ws-1"),
}

# 조회 함수별로 정상 응답 모양
LOOKUP_BODIES: dict[str, dict[str, Any]] = {
    "list_models": {"data": [{"id": "mistralai/mistral-nemo"}]},
    "get_model_endpoints": {"data": {"endpoints": [{"provider_name": "DekaLLM"}]}},
    "get_generation": {"data": {"total_cost": 0.1}},
    "get_key_usage": {"data": {"usage": 0.1}},
    "list_keys": {"data": [{"hash": "h1", "name": "key"}]},
}

ALL_LOOKUPS = list(LOOKUP_CALLS)


def respond_with(name: str) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=LOOKUP_BODIES[name])

    return handler


# ---------------------------------------------------------------
# 요청 모양
# ---------------------------------------------------------------
async def test_모델_목록은_Key_없이_공개_주소로_부른다(factory: ClientFactory) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_with("list_models")(request)

    result = await factory(handler).list_models()

    request = captured[0]
    assert request.method == "GET"
    assert str(request.url) == f"{OPENROUTER_BASE_URL}/models"
    assert "Authorization" not in request.headers
    assert result.ok
    assert result.data is not None
    assert result.data[0].model_id == "mistralai/mistral-nemo"


async def test_모델의_업체_목록은_Key_없이_모델_ID_경로로_부른다(
    factory: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_with("get_model_endpoints")(request)

    result = await factory(handler).get_model_endpoints("mistralai/mistral-nemo")

    request = captured[0]
    assert request.method == "GET"
    expected_url = f"{OPENROUTER_BASE_URL}/models/mistralai/mistral-nemo/endpoints"
    assert str(request.url) == expected_url
    assert "Authorization" not in request.headers
    assert result.ok
    assert result.data is not None
    assert [item.provider_name for item in result.data] == ["DekaLLM"]


async def test_모델의_업체_목록_404는_http_status로_알리고_다시_보내지_않는다(
    factory: ClientFactory,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(404, json={"error": {"code": 404}})

    result = await factory(handler).get_model_endpoints("a/gone")

    assert not result.ok
    assert result.http_status == 404
    assert call_count == 1
    assert factory.sleeps == []


async def test_호출_조회는_generation_ID와_Key로_부른다(factory: ClientFactory) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_with("get_generation")(request)

    result = await factory(handler).get_generation("gen-abc")

    request = captured[0]
    assert request.url.path == "/api/v1/generation"
    assert request.url.params["id"] == "gen-abc"
    assert request.headers["Authorization"] == f"Bearer {FAKE_API_KEY}"
    assert result.data is not None
    assert result.data.found is True
    assert result.data.total_cost == Decimal("0.1")


async def test_Key_사용량은_현재_Key로_부른다(factory: ClientFactory) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_with("get_key_usage")(request)

    result = await factory(handler).get_key_usage()

    request = captured[0]
    assert request.url.path == "/api/v1/key"
    assert request.headers["Authorization"] == f"Bearer {FAKE_API_KEY}"
    assert result.data is not None
    assert result.data.usage == Decimal("0.1")


async def test_Key_목록은_Management_Key와_workspace로_부른다(
    factory: ClientFactory,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_with("list_keys")(request)

    result = await factory(handler).list_keys("ws-1")

    request = captured[0]
    assert request.url.path == "/api/v1/keys"
    assert request.url.params["workspace_id"] == "ws-1"
    assert request.headers["Authorization"] == f"Bearer {FAKE_MANAGEMENT_KEY}"
    assert result.data is not None
    assert result.data[0].key_hash == "h1"


async def test_Management_Key가_없으면_요청을_보내지_않고_AUTH_ERROR다(
    factory: ClientFactory,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return respond_with("list_keys")(request)

    result = await factory(handler, management_key=None).list_keys("ws-1")

    assert call_count == 0
    assert not result.ok
    assert result.error_type == ErrorType.AUTH_ERROR
    assert result.error_message


@pytest.mark.parametrize("name", ALL_LOOKUPS)
async def test_모든_조회에_timeout을_명시한다(
    factory: ClientFactory, name: str
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return respond_with(name)(request)

    await LOOKUP_CALLS[name](factory(handler))

    timeout = LOOKUP_TIMEOUT_SECONDS
    expected = {"connect": timeout, "read": timeout, "write": timeout, "pool": timeout}
    assert captured[0].extensions["timeout"] == expected


# ---------------------------------------------------------------
# 호출 조회의 404는 오류가 아니라 "없음"이다
# ---------------------------------------------------------------
async def test_호출_조회의_404는_found_False이고_다시_보내지_않는다(
    factory: ClientFactory,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(404, json={"error": {"code": 404}})

    result = await factory(handler).get_generation("gen-abc")

    assert result.ok
    assert result.data is not None
    assert result.data.found is False
    assert result.http_status == 404
    assert call_count == 1
    assert factory.sleeps == []


# ---------------------------------------------------------------
# 네트워크 오류일 때만 다시 보낸다 (비용이 없는 조회)
# ---------------------------------------------------------------
@pytest.mark.parametrize("name", ALL_LOOKUPS)
async def test_네트워크_오류가_나면_다시_보내고_성공하면_결과를_돌려준다(
    factory: ClientFactory, name: str
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < LOOKUP_MAX_ATTEMPTS:
            raise httpx.ConnectError("connection failed", request=request)
        return respond_with(name)(request)

    result = await LOOKUP_CALLS[name](factory(handler))

    assert result.ok
    assert call_count == LOOKUP_MAX_ATTEMPTS
    expected_sleeps = [LOOKUP_RETRY_DELAY_SECONDS] * (LOOKUP_MAX_ATTEMPTS - 1)
    assert factory.sleeps == expected_sleeps


@pytest.mark.parametrize(
    ("error_class", "expected"),
    [
        (httpx.ConnectError, ErrorType.NETWORK_ERROR),
        (httpx.ReadTimeout, ErrorType.TIMEOUT_ERROR),
    ],
)
async def test_계속_실패하면_정해진_횟수만_보내고_오류_결과를_돌려준다(
    factory: ClientFactory,
    error_class: type[httpx.RequestError],
    expected: ErrorType,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise error_class("failed", request=request)

    result = await factory(handler).list_models()

    assert not result.ok
    assert result.error_type == expected
    assert result.error_message == USER_MESSAGES[expected]
    assert result.http_status is None
    assert call_count == LOOKUP_MAX_ATTEMPTS
    assert len(factory.sleeps) == LOOKUP_MAX_ATTEMPTS - 1


# ---------------------------------------------------------------
# HTTP 오류와 이상한 응답은 다시 보내지 않는다
# ---------------------------------------------------------------
@pytest.mark.parametrize("name", ALL_LOOKUPS)
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ErrorType.AUTH_ERROR),
        (429, ErrorType.RATE_LIMIT),
        (500, ErrorType.PROVIDER_ERROR),
    ],
)
async def test_HTTP_오류는_다시_보내지_않고_오류_유형을_돌려준다(
    factory: ClientFactory, name: str, status_code: int, expected: ErrorType
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(status_code, json={"error": {"code": status_code}})

    result = await LOOKUP_CALLS[name](factory(handler))

    assert not result.ok
    assert result.error_type == expected
    assert result.http_status == status_code
    assert call_count == 1
    assert factory.sleeps == []


@pytest.mark.parametrize("name", ALL_LOOKUPS)
async def test_200인데_JSON이_아니면_INVALID_RESPONSE다(
    factory: ClientFactory, name: str
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, text="이것은 JSON이 아니다")

    result = await LOOKUP_CALLS[name](factory(handler))

    assert not result.ok
    assert result.error_type == ErrorType.INVALID_RESPONSE
    assert result.http_status == 200
    assert call_count == 1


@pytest.mark.parametrize("name", ALL_LOOKUPS)
async def test_200인데_data_모양이_틀리면_INVALID_RESPONSE다(
    factory: ClientFactory, name: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "문자열"})

    result = await LOOKUP_CALLS[name](factory(handler))

    assert not result.ok
    assert result.error_type == ErrorType.INVALID_RESPONSE


# ---------------------------------------------------------------
# Key는 결과나 로그에 남기지 않는다
# ---------------------------------------------------------------
@pytest.mark.parametrize("name", ALL_LOOKUPS)
async def test_실패_결과와_로그에_Key가_남지_않는다(
    factory: ClientFactory, caplog: pytest.LogCaptureFixture, name: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        message = f"cannot reach server with {FAKE_API_KEY} {FAKE_MANAGEMENT_KEY}"
        raise httpx.ConnectError(message, request=request)

    caplog.set_level(logging.DEBUG)

    result = await LOOKUP_CALLS[name](factory(handler))

    dumped = json.dumps(result.__dict__, default=str)
    for key in (FAKE_API_KEY, FAKE_MANAGEMENT_KEY):
        assert key not in dumped
        assert key not in caplog.text

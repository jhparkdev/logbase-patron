"""services/command_code_client.py 테스트. 실제 Command Code를 부르지 않고 가짜 서버로 검사한다."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.schemas.command_code import CommandCodeStatus
from app.services.command_code_client import BASE_URL, PATHS, CommandCodeClient

# 테스트용 가짜 값. 로그와 결과에 드러나는지 찾을 표식으로 쓴다.
API_KEY = "user_test-only-not-a-real-key"

SUMMARY_TEXT = (
    '{"totalCount": 2379, "totalCredits": 27.6518301021, "totalTokensIn": 816632167,'
    ' "totalTokensOut": 1987270, "periodStart": "2026-10-20T02:04:33.000Z",'
    ' "daily": []}'
)
CREDITS_TEXT = '{"credits": {"monthlyCredits": 62.3745912155, "purchasedCredits": 0}}'
SUBSCRIPTION_TEXT = (
    '{"success": true, "data": {"status": "active",'
    ' "currentPeriodStart": "2026-10-20T02:04:33.000Z",'
    ' "currentPeriodEnd": "2026-11-20T02:04:33.000Z"}}'
)
EXPIRED_TEXT = (
    '{"success": false, "error": {"code": "UNAUTHORIZED", "status": 401,'
    ' "message": "Your API key has expired."}}'
)
INVALID_TEXT = (
    '{"success": false, "error": {"code": "UNAUTHORIZED", "status": 401,'
    ' "message": "Invalid \'Authorization\' header or token."}}'
)
OK_TEXTS = dict(
    zip(PATHS, (SUMMARY_TEXT, CREDITS_TEXT, SUBSCRIPTION_TEXT), strict=True)
)


def _reply(status_code: int, text: str) -> httpx.Response:
    return httpx.Response(
        status_code, text=text, headers={"Content-Type": "application/json"}
    )


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> CommandCodeClient:
    transport = httpx.MockTransport(handler)
    return CommandCodeClient(http_client=httpx.AsyncClient(transport=transport))


def _serving(**overrides: httpx.Response) -> Callable[[httpx.Request], httpx.Response]:
    """경로별 응답. overrides의 키는 PATHS의 위치(summary, credits, subscription)이다."""
    names = dict(zip(("summary", "credits", "subscription"), PATHS, strict=True))
    replaced = {names[name]: reply for name, reply in overrides.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in replaced:
            return replaced[path]
        return _reply(200, OK_TEXTS[path])

    return handler


async def test_세_곳을_모두_읽으면_OK와_사용량을_돌려준다() -> None:
    result = await _client(_serving()).fetch(API_KEY)

    assert result.status == CommandCodeStatus.OK
    assert result.snapshot is not None
    assert result.snapshot.used_credits == Decimal("27.6518301021")
    assert result.snapshot.remaining_credits == Decimal("62.3745912155")
    assert result.snapshot.request_count == 2379
    assert result.snapshot.period_end == datetime(2026, 11, 20, 2, 4, 33, tzinfo=UTC)


async def test_금액은_float_오차_없이_자릿수_그대로_읽는다() -> None:
    summary = SUMMARY_TEXT.replace("27.6518301021", "0.1234567890123")

    result = await _client(_serving(summary=_reply(200, summary))).fetch(API_KEY)

    assert result.snapshot is not None
    assert result.snapshot.used_credits == Decimal("0.1234567890123")


async def test_세_경로를_Bearer_Key와_User_Agent를_붙여_부른다() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _reply(200, OK_TEXTS[request.url.path])

    await _client(handler).fetch(API_KEY)

    assert sorted(request.url.path for request in seen) == sorted(PATHS)
    for request in seen:
        assert request.method == "GET"
        assert str(request.url).startswith(BASE_URL)
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        # 없으면 403이 날 수 있다고 개발자가 알려 줬다
        assert request.headers["User-Agent"].strip() != ""


async def test_만료된_키의_401은_KEY_EXPIRED이다() -> None:
    client = _client(_serving(summary=_reply(401, EXPIRED_TEXT)))

    result = await client.fetch(API_KEY)

    assert result.status == CommandCodeStatus.KEY_EXPIRED
    assert result.snapshot is None


async def test_틀린_키의_401은_KEY_INVALID이다() -> None:
    client = _client(_serving(summary=_reply(401, INVALID_TEXT)))

    result = await client.fetch(API_KEY)

    assert result.status == CommandCodeStatus.KEY_INVALID
    assert result.snapshot is None


async def test_세_경로_중_하나만_401이어도_그_상태로_돌려준다() -> None:
    client = _client(_serving(subscription=_reply(401, EXPIRED_TEXT)))

    result = await client.fetch(API_KEY)

    assert result.status == CommandCodeStatus.KEY_EXPIRED


@pytest.mark.parametrize("status_code", [403, 404, 429, 500, 503])
async def test_그_밖의_HTTP_오류는_FETCH_FAILED이다(status_code: int) -> None:
    client = _client(_serving(credits=_reply(status_code, "{}")))

    result = await client.fetch(API_KEY)

    assert result.status == CommandCodeStatus.FETCH_FAILED
    assert result.snapshot is None


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("x"), httpx.ReadTimeout("x"), httpx.ReadError("x")]
)
async def test_연결_실패와_시간_초과는_FETCH_FAILED이다(error: httpx.HTTPError) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    result = await _client(handler).fetch(API_KEY)

    assert result.status == CommandCodeStatus.FETCH_FAILED
    assert result.snapshot is None


@pytest.mark.parametrize(
    "text",
    [
        "<html>점검 중</html>",
        "",
        "[]",
        '{"unexpected": 1}',
    ],
)
async def test_200이어도_예상한_모양이_아니면_FETCH_FAILED이다(text: str) -> None:
    client = _client(_serving(summary=_reply(200, text)))

    result = await client.fetch(API_KEY)

    assert result.status == CommandCodeStatus.FETCH_FAILED
    assert result.snapshot is None


async def test_실패해도_Key를_로그와_결과에_남기지_않는다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    client = _client(_serving(summary=_reply(401, INVALID_TEXT)))

    result = await client.fetch(API_KEY)

    assert API_KEY not in repr(result)
    assert API_KEY not in caplog.text

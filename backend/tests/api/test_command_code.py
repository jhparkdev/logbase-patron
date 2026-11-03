"""GET /api/usage/internal/command-code 테스트. 구독료 관리 카드 안의 구성원별 Command Code 사용량을 확인한다."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.command_code_deps import get_member_keys, get_usage_fetcher
from app.schemas.command_code import CommandCodeStatus
from app.services.command_code_result import FetchResult, UsageSnapshot
from tests.db_helpers import Factory

URL = "/api/usage/internal/command-code"
# 테스트용 가짜 값. 응답에 드러나는지 찾을 표식으로 쓴다
SECRET = "cc-test-only-not-a-real-key"


class FakeFetch:
    def __init__(self, results: dict[str, FetchResult]) -> None:
        self.results = results

    async def __call__(self, api_key: str) -> FetchResult:
        return self.results[api_key]


@pytest.fixture
def snapshot() -> UsageSnapshot:
    return UsageSnapshot(
        used_credits=Decimal("27.6518301021"),
        request_count=2379,
        input_tokens=816632167,
        output_tokens=1987270,
        remaining_credits=Decimal("62.3745912155"),
        period_start=datetime(2026, 10, 20, 2, 4, 33, tzinfo=UTC),
        period_end=datetime(2026, 11, 20, 2, 4, 33, tzinfo=UTC),
    )


@pytest.fixture
def fetch(app: FastAPI, snapshot: UsageSnapshot) -> FakeFetch:
    """실제 Command Code를 부르지 않게 바꿔 끼운다. 설정의 실제 Key도 쓰지 않는다."""
    result = FetchResult(status=CommandCodeStatus.OK, snapshot=snapshot)
    fake = FakeFetch({SECRET: result})
    keys = {"COMMAND_CODE_KEY_HONG": SECRET}
    app.dependency_overrides[get_usage_fetcher] = lambda: fake
    app.dependency_overrides[get_member_keys] = lambda: keys
    return fake


async def test_구성원_한_줄에_표에_쓸_값을_모두_담는다(
    client: AsyncClient, factory: Factory, fetch: FakeFetch, now: datetime
) -> None:
    await factory.command_code_key(
        member_name="홍길동", secret_ref="COMMAND_CODE_KEY_HONG"
    )

    response = await client.get(URL)

    assert response.status_code == status.HTTP_200_OK
    [item] = response.json()["items"]
    assert item == {
        "member_name": "홍길동",
        "status": "OK",
        "used_credits": "27.6518301021",
        "request_count": 2379,
        "input_tokens": 816632167,
        "output_tokens": 1987270,
        "remaining_credits": "62.3745912155",
        "period_start": "2026-10-20T02:04:33Z",
        "period_end": "2026-11-20T02:04:33Z",
        "fetched_at": item["fetched_at"],
    }
    assert datetime.fromisoformat(item["fetched_at"]) == now


async def test_금액은_문자열로_준다(
    client: AsyncClient, factory: Factory, fetch: FakeFetch
) -> None:
    await factory.command_code_key(
        member_name="홍길동", secret_ref="COMMAND_CODE_KEY_HONG"
    )

    [item] = (await client.get(URL)).json()["items"]

    assert isinstance(item["used_credits"], str)
    assert isinstance(item["remaining_credits"], str)


async def test_Key_원문과_Key_이름을_응답에_넣지_않는다(
    client: AsyncClient, factory: Factory, fetch: FakeFetch
) -> None:
    await factory.command_code_key(
        member_name="홍길동", secret_ref="COMMAND_CODE_KEY_HONG"
    )

    response = await client.get(URL)

    assert SECRET not in response.text
    assert "COMMAND_CODE_KEY" not in response.text
    assert "secret_ref" not in response.text


async def test_읽지_못한_구성원은_상태만_알려주고_값은_null이다(
    client: AsyncClient, factory: Factory, fetch: FakeFetch
) -> None:
    await factory.command_code_key(
        member_name="홍길동", secret_ref="COMMAND_CODE_KEY_HONG"
    )
    await factory.command_code_key(
        member_name="박영희", secret_ref="COMMAND_CODE_KEY_PARK"
    )

    items = (await client.get(URL)).json()["items"]

    by_name = {item["member_name"]: item for item in items}
    assert by_name["홍길동"]["status"] == "OK"
    missing = by_name["박영희"]
    assert missing["status"] == "KEY_MISSING"
    assert missing["used_credits"] is None
    assert missing["request_count"] is None
    assert missing["remaining_credits"] is None
    assert missing["period_end"] is None


async def test_등록된_구성원이_없으면_빈_목록이다(
    client: AsyncClient, fetch: FakeFetch
) -> None:
    response = await client.get(URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"items": []}


def test_OpenAPI의_상태_값에_다섯_가지가_모두_있다(app: FastAPI) -> None:
    schema = app.openapi()

    statuses = schema["components"]["schemas"]["CommandCodeStatus"]["enum"]
    assert sorted(statuses) == sorted(item.value for item in CommandCodeStatus)

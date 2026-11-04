"""GET /api/models/openrouter/new 테스트. 모델 관리 화면에서 보여 줄 신규 모델 알림을 확인한다."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.model_deps import get_openrouter_catalog
from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from tests.api.model_helpers import FakeCatalog, info
from tests.db_helpers import Factory

# 로그인한 사용자만 부를 수 있는 API다. 로그인 경계는 tests/test_main.py 에서 확인한다
pytestmark = pytest.mark.usefixtures("signed_in")

URL = "/api/models/openrouter/new"


@pytest.fixture
def catalog(app: FastAPI) -> FakeCatalog:
    fake = FakeCatalog([])
    app.dependency_overrides[get_openrouter_catalog] = lambda: fake
    return fake


def ids(body: dict[str, Any]) -> list[str]:
    return [item["openrouter_model_id"] for item in body["items"]]


def days_ago(now: datetime, days: float) -> datetime:
    return now - timedelta(days=days)


async def test_모델_한_건의_필드를_돌려준다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [
        info(
            "vendor/a",
            name="Vendor: A",
            created_at=days_ago(now, 1),
            pricing={
                "prompt": Decimal("0.0000001"),
                "completion": Decimal("0.0000004"),
            },
            input_modalities=["text", "image"],
            output_modalities=["text"],
            context_length=1000,
        )
    ]

    response = await client.get(URL)

    assert response.status_code == status.HTTP_200_OK
    [item] = response.json()["items"]
    assert item == {
        "openrouter_model_id": "vendor/a",
        "name": "Vendor: A",
        "provider": "vendor",
        "created_at": item["created_at"],
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "context_length": 1000,
        "input_price_per_token": "0.0000001",
        "output_price_per_token": "0.0000004",
    }
    assert datetime.fromisoformat(item["created_at"]) == days_ago(now, 1)


async def test_조건을_보내지_않으면_5일과_5개가_기본이다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [info(f"v/m{n}", created_at=days_ago(now, 1)) for n in range(7)]
    catalog.models.append(info("v/old", created_at=days_ago(now, 6)))

    body = (await client.get(URL)).json()

    assert (body["days"], body["total"]) == (5, 7)
    assert len(body["items"]) == 5


async def test_기간과_개수_조건을_따른다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [
        info("v/a", created_at=days_ago(now, 1)),
        info("v/b", created_at=days_ago(now, 5)),
        info("v/c", created_at=days_ago(now, 20)),
    ]

    body = (await client.get(URL, params={"days": 10, "limit": 1})).json()

    assert ids(body) == ["v/a"]
    assert (body["days"], body["total"]) == (10, 2)


async def test_최근에_올라온_순으로_준다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [
        info("v/old", created_at=days_ago(now, 4)),
        info("v/new", created_at=days_ago(now, 1)),
        info("v/mid", created_at=days_ago(now, 2)),
    ]

    assert ids((await client.get(URL)).json()) == ["v/new", "v/mid", "v/old"]


async def test_이미_등록한_모델과_올라온_시각을_모르는_모델은_뺀다(
    client: AsyncClient, catalog: FakeCatalog, factory: Factory, now: datetime
) -> None:
    await factory.model(openrouter_model_id="v/registered")
    catalog.models = [
        info("v/registered", created_at=days_ago(now, 1)),
        info("v/unknown", created_at=None),
        info("v/new", created_at=days_ago(now, 1)),
    ]

    body = (await client.get(URL)).json()

    assert ids(body) == ["v/new"]
    assert body["total"] == 1


async def test_가격을_모르면_null이고_이름이_없으면_모델_ID가_이름이다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [info("v/a", name=None, pricing={}, created_at=days_ago(now, 1))]

    [item] = (await client.get(URL)).json()["items"]

    assert item["name"] == "v/a"
    assert item["input_price_per_token"] is None
    assert item["output_price_per_token"] is None


async def test_새_모델이_없으면_빈_목록이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    body = (await client.get(URL)).json()

    assert (body["items"], body["total"]) == ([], 0)


async def test_OpenRouter에서_목록을_받지_못하면_502이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = None

    response = await client.get(URL)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json() == {
        "code": ModelErrorCode.OPENROUTER_UNAVAILABLE,
        "message": ERROR_SPECS[ModelErrorCode.OPENROUTER_UNAVAILABLE].message,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"days": 0},
        {"days": 366},
        {"days": "many"},
        {"limit": 0},
        {"limit": 51},
        {"limit": "all"},
        {"page": 2},
    ],
    ids=["0일", "366일", "일수가 글자", "0개", "51개", "개수가 글자", "모르는 조건"],
)
async def test_잘못된_조건은_422이다(
    client: AsyncClient, catalog: FakeCatalog, params: dict[str, Any]
) -> None:
    response = await client.get(URL, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize(
    "params", [{"days": 1, "limit": 1}, {"days": 365, "limit": 50}]
)
async def test_조건의_양쪽_끝_값은_받는다(
    client: AsyncClient, catalog: FakeCatalog, params: dict[str, Any]
) -> None:
    assert (await client.get(URL, params=params)).status_code == status.HTTP_200_OK


# ---------------------------------------------------------------
# 신규 모델만 보기: 등록 패널이 알림에서 열릴 때 쓰는 GET /api/models/openrouter?new_days=
# ---------------------------------------------------------------
SEARCH = "/api/models/openrouter"


async def test_new_days를_보내면_최근_모델만_최신순으로_주고_출시일을_담는다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [
        info("v/old", created_at=days_ago(now, 40)),
        info("v/mid", created_at=days_ago(now, 4)),
        info("v/new", created_at=days_ago(now, 1)),
        info("v/unknown", created_at=None),
    ]

    body = (await client.get(SEARCH, params={"new_days": 30})).json()

    assert ids(body) == ["v/new", "v/mid"]
    assert body["total"] == 2
    assert datetime.fromisoformat(body["items"][0]["created_at"]) == days_ago(now, 1)
    assert all(item["registered"] is False for item in body["items"])


async def test_new_days를_보내면_이미_등록한_모델은_목록에서_빠진다(
    client: AsyncClient, catalog: FakeCatalog, factory: Factory, now: datetime
) -> None:
    await factory.model(openrouter_model_id="v/registered")
    catalog.models = [
        info("v/registered", created_at=days_ago(now, 1)),
        info("v/new", created_at=days_ago(now, 2)),
    ]

    body = (await client.get(SEARCH, params={"new_days": 30})).json()

    assert ids(body) == ["v/new"]
    assert body["total"] == 1


async def test_new_days는_검색어와_페이지와_함께_쓸_수_있다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [
        info(f"acme/m{number}", created_at=days_ago(now, number))
        for number in range(1, 6)
    ]
    catalog.models.append(info("other/x", created_at=days_ago(now, 1)))

    body = (
        await client.get(
            SEARCH,
            params={"new_days": 30, "q": "acme", "page": 2, "page_size": 2},
        )
    ).json()

    assert ids(body) == ["acme/m3", "acme/m4"]
    assert (body["page"], body["page_size"], body["total"]) == (2, 2, 5)


async def test_new_days를_보내지_않으면_출시일과_상관없이_모델_ID순_전체이다(
    client: AsyncClient, catalog: FakeCatalog, now: datetime
) -> None:
    catalog.models = [
        info("b/old", created_at=days_ago(now, 400)),
        info("a/unknown", created_at=None),
    ]

    body = (await client.get(SEARCH)).json()

    assert ids(body) == ["a/unknown", "b/old"]
    assert [item["created_at"] is None for item in body["items"]] == [True, False]


@pytest.mark.parametrize("days", [0, 366, "many"])
async def test_new_days가_범위를_벗어나면_422이다(
    client: AsyncClient, catalog: FakeCatalog, days: Any
) -> None:
    response = await client.get(SEARCH, params={"new_days": days})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

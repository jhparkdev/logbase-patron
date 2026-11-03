"""GET /api/models/openrouter 테스트. 신규 등록 때 OpenRouter 모델을 찾는 검색을 확인한다."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.model_deps import get_openrouter_catalog
from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from app.schemas.models import MAX_PAGE_SIZE
from tests.api.model_helpers import FakeCatalog, info
from tests.db_helpers import Factory

SEARCH = "/api/models/openrouter"


@pytest.fixture
def catalog(app: FastAPI) -> FakeCatalog:
    fake = FakeCatalog([])
    app.dependency_overrides[get_openrouter_catalog] = lambda: fake
    return fake


def ids(body: dict[str, Any]) -> list[str]:
    return [item["openrouter_model_id"] for item in body["items"]]


async def test_검색어가_없으면_모델_ID순으로_전체를_돌려준다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [info("b/two"), info("a/one")]

    response = await client.get(SEARCH)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert ids(body) == ["a/one", "b/two"]
    assert (body["page"], body["total"]) == (1, 2)


async def test_모델_한_건의_필드를_돌려준다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [
        info(
            "vendor/a",
            name="Vendor: A",
            pricing={
                "prompt": Decimal("0.0000001"),
                "completion": Decimal("0.0000004"),
            },
            input_modalities=["text", "image"],
            output_modalities=["text"],
            context_length=1000,
            supported_parameters=["response_format", "tools"],
        )
    ]

    item = (await client.get(SEARCH)).json()["items"][0]

    assert item == {
        "openrouter_model_id": "vendor/a",
        "name": "Vendor: A",
        "provider": "vendor",
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "context_length": 1000,
        "input_price_per_token": "0.0000001",
        "output_price_per_token": "0.0000004",
        "supports_json_schema": True,
        "supports_tools": True,
        "registered": False,
        "created_at": None,
    }


async def test_이름이_없으면_모델_ID가_이름이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [info("vendor/a", name=None)]

    item = (await client.get(SEARCH)).json()["items"][0]

    assert item["name"] == "vendor/a"


@pytest.mark.parametrize(
    "pricing",
    [{}, {"prompt": Decimal(-1), "completion": Decimal(-1)}],
    ids=["가격 항목 없음", "음수 가격"],
)
async def test_가격을_알_수_없으면_null이다(
    client: AsyncClient, catalog: FakeCatalog, pricing: dict[str, Decimal]
) -> None:
    catalog.models = [info("vendor/a", pricing=pricing)]

    item = (await client.get(SEARCH)).json()["items"][0]

    assert item["input_price_per_token"] is None
    assert item["output_price_per_token"] is None


async def test_작은_단가도_지수_표기가_아닌_숫자_문자열로_돌려준다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    pricing = {"prompt": Decimal("3E-8"), "completion": Decimal(0)}
    catalog.models = [info("vendor/a", pricing=pricing)]

    item = (await client.get(SEARCH)).json()["items"][0]

    assert item["input_price_per_token"] == "0.00000003"
    assert item["output_price_per_token"] == "0"


async def test_검색어가_모델_ID나_이름에_들어_있으면_찾는다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [
        info("openai/gpt-4o", name="GPT-4o"),
        info("acme/unique-id", name="Other"),
        info("vendor/none", name="Nothing"),
    ]

    by_name = (await client.get(SEARCH, params={"q": "GPT"})).json()
    by_id = (await client.get(SEARCH, params={"q": "UNIQUE"})).json()

    assert ids(by_name) == ["openai/gpt-4o"]
    assert ids(by_id) == ["acme/unique-id"]


async def test_이미_등록된_모델은_registered가_true이다(
    client: AsyncClient, catalog: FakeCatalog, factory: Factory
) -> None:
    await factory.model(openrouter_model_id="vendor/a", provider="vendor")
    catalog.models = [info("vendor/a"), info("vendor/b")]

    items = (await client.get(SEARCH)).json()["items"]

    assert {item["openrouter_model_id"]: item["registered"] for item in items} == {
        "vendor/a": True,
        "vendor/b": False,
    }


async def test_페이지로_나누어_total은_찾은_전체_개수이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [info(f"vendor/{number}") for number in range(1, 4)]

    body = (await client.get(SEARCH, params={"page": 2, "page_size": 2})).json()

    assert ids(body) == ["vendor/3"]
    assert (body["page"], body["page_size"], body["total"]) == (2, 2, 3)


async def test_OpenRouter에서_목록을_받지_못하면_502이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = None

    response = await client.get(SEARCH)

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json() == {
        "code": ModelErrorCode.OPENROUTER_UNAVAILABLE,
        "message": ERROR_SPECS[ModelErrorCode.OPENROUTER_UNAVAILABLE].message,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"q": ""},
        {"q": "a\x00b"},
        {"page": 0},
        {"page_size": MAX_PAGE_SIZE + 1},
        {"unknown_param": "1"},
    ],
)
async def test_허용하지_않는_조건은_422이다(
    client: AsyncClient, catalog: FakeCatalog, params: dict[str, Any]
) -> None:
    response = await client.get(SEARCH, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"

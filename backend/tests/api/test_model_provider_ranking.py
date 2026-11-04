"""GET /api/models/{model_id}/execution-providers/ranking 테스트. 업체를 예상 총비용이 싼 순서로 알려 준다."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.model_deps import get_endpoint_catalog
from app.openrouter.lookup_result import EndpointInfo
from app.schemas.common import ErrorCode
from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from app.services.execution_provider_catalog import ModelNotOnOpenRouterError
from app.services.openrouter_catalog import OpenRouterUnavailableError
from tests.api.model_helpers import FakeEndpointCatalog
from tests.db_helpers import Factory

MODELS = "/api/models"
TOKENS = {"input_tokens": 1000, "output_tokens": 500}


def path(model_id: int | str) -> str:
    return f"{MODELS}/{model_id}/execution-providers/ranking"


def endpoint(name: str, prompt: str = "0.000002", **fields: Any) -> EndpointInfo:
    pricing = {
        "prompt": Decimal(prompt),
        "completion": Decimal("0.00001"),
        **fields.pop("pricing", {}),
    }
    return EndpointInfo(
        provider_name=name,
        status=fields.pop("status", 0),
        uptime_last_1d=Decimal(fields.pop("uptime", "99.5")),
        pricing=pricing,
    )


@pytest.fixture
def endpoints(app: FastAPI) -> FakeEndpointCatalog:
    fake = FakeEndpointCatalog([])
    app.dependency_overrides[get_endpoint_catalog] = lambda: fake
    return fake


async def test_싼_순서로_예상_비용과_단가를_문자열로_돌려준다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model(openrouter_model_id="mistralai/mistral-nemo")
    endpoints.endpoints = [
        endpoint("Pricey", prompt="0.000005"),
        endpoint(
            "Cheap",
            prompt="0.000001",
            pricing={"input_cache_read": Decimal("0.0000001")},
        ),
    ]

    response = await client.get(path(model["model_id"]), params=TOKENS)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert [item["execution_provider"] for item in body["items"]] == [
        "Cheap",
        "Pricey",
    ]
    assert body["items"][0] == {
        "execution_provider": "Cheap",
        "expected_cost_usd": "0.006",
        "input_price_per_token": "0.000001",
        "output_price_per_token": "0.00001",
        "cache_read_price_per_token": "0.0000001",
        "cache_write_price_per_token": None,
        "supports_caching": True,
    }
    assert body["excluded"] == []
    assert endpoints.asked == ["mistralai/mistral-nemo"]


async def test_작은_비용도_지수_표기_없이_문자열로_준다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.endpoints = [endpoint("A", prompt="0.0000000042")]

    response = await client.get(
        path(model["model_id"]), params={"input_tokens": 1, "output_tokens": 0}
    )

    item = response.json()["items"][0]
    assert item["expected_cost_usd"] == "0.0000000042"
    assert item["input_price_per_token"] == "0.0000000042"


async def test_캐시_적중_비율을_보내면_캐시_단가가_있는_업체가_유리해진다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.endpoints = [
        endpoint("NoCache", prompt="0.000001"),
        endpoint(
            "Cache",
            prompt="0.0000015",
            pricing={"input_cache_read": Decimal("0.00000005")},
        ),
    ]
    params = {"input_tokens": 10000, "output_tokens": 100}

    plain = (await client.get(path(model["model_id"]), params=params)).json()
    cached = (
        await client.get(
            path(model["model_id"]), params={**params, "cache_hit_ratio": "0.9"}
        )
    ).json()

    assert plain["items"][0]["execution_provider"] == "NoCache"
    assert cached["items"][0]["execution_provider"] == "Cache"


async def test_상태나_가동률이_나쁜_업체는_이유와_함께_제외한다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.endpoints = [
        endpoint("Good"),
        endpoint("Down", status=-1),
        endpoint("Flaky", uptime="50"),
        EndpointInfo(provider_name="NoPrice", status=0),
    ]

    body = (await client.get(path(model["model_id"]), params=TOKENS)).json()

    assert [item["execution_provider"] for item in body["items"]] == ["Good"]
    assert {
        item["execution_provider"]: item["reason"] for item in body["excluded"]
    } == {
        "Down": "STATUS_NOT_OK",
        "Flaky": "LOW_UPTIME",
        "NoPrice": "PRICE_UNKNOWN",
    }


async def test_가동률_기준은_요청으로_바꿀_수_있다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.endpoints = [endpoint("Flaky", uptime="85")]

    default = (await client.get(path(model["model_id"]), params=TOKENS)).json()
    relaxed = (
        await client.get(path(model["model_id"]), params={**TOKENS, "min_uptime": 80})
    ).json()

    assert default["items"] == []
    assert [item["execution_provider"] for item in relaxed["items"]] == ["Flaky"]


async def test_업체가_없으면_빈_목록이다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()

    response = await client.get(path(model["model_id"]), params=TOKENS)

    assert response.json() == {"items": [], "excluded": []}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"input_tokens": 1000},
        {"output_tokens": 500},
        {"input_tokens": -1, "output_tokens": 500},
        {"input_tokens": 1000, "output_tokens": -1},
        {"input_tokens": 1000, "output_tokens": 500, "cache_hit_ratio": "1.5"},
        {"input_tokens": 1000, "output_tokens": 500, "cache_hit_ratio": "-0.1"},
        {"input_tokens": 1000, "output_tokens": 500, "min_uptime": 101},
        {"input_tokens": 1000, "output_tokens": 500, "min_uptime": -1},
        {"input_tokens": "many", "output_tokens": 500},
        {"input_tokens": 1000, "output_tokens": 500, "unknown": 1},
    ],
    ids=[
        "아무것도 없음",
        "출력 없음",
        "입력 없음",
        "음수 입력",
        "음수 출력",
        "적중 비율 1 초과",
        "적중 비율 음수",
        "가동률 100 초과",
        "가동률 음수",
        "글자 입력",
        "모르는 조건",
    ],
)
async def test_조건이_빠졌거나_범위를_벗어나면_422이고_OpenRouter에_묻지_않는다(
    client: AsyncClient,
    factory: Factory,
    endpoints: FakeEndpointCatalog,
    params: dict[str, Any],
) -> None:
    model = await factory.model()

    response = await client.get(path(model["model_id"]), params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert endpoints.asked == []


@pytest.mark.parametrize(
    "extra",
    [
        {"cache_hit_ratio": 0},
        {"cache_hit_ratio": 1},
        {"min_uptime": 0},
        {"min_uptime": 100},
    ],
)
async def test_조건의_양쪽_끝_값은_받는다(
    client: AsyncClient,
    factory: Factory,
    endpoints: FakeEndpointCatalog,
    extra: dict[str, Any],
) -> None:
    model = await factory.model()

    response = await client.get(path(model["model_id"]), params={**TOKENS, **extra})

    assert response.status_code == status.HTTP_200_OK


async def test_등록되지_않은_모델은_404이고_OpenRouter에_묻지_않는다(
    client: AsyncClient, endpoints: FakeEndpointCatalog
) -> None:
    response = await client.get(path(999999), params=TOKENS)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == ErrorCode.NOT_FOUND
    assert endpoints.asked == []


async def test_OpenRouter가_모델을_모르면_전용_코드의_404다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.error = ModelNotOnOpenRouterError()

    response = await client.get(path(model["model_id"]), params=TOKENS)

    code = ModelErrorCode.OPENROUTER_MODEL_NOT_FOUND
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": code, "message": ERROR_SPECS[code].message}


async def test_업체_목록을_받지_못하면_502다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.error = OpenRouterUnavailableError()

    response = await client.get(path(model["model_id"]), params=TOKENS)

    code = ModelErrorCode.EXECUTION_PROVIDERS_UNAVAILABLE
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json() == {"code": code, "message": ERROR_SPECS[code].message}

"""GET /api/models/{model_id}/execution-providers 테스트. 비교 실행에서 고를 서버 업체 선택지를 확인한다."""

from decimal import Decimal

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.api.model_deps import get_endpoint_catalog
from app.openrouter.lookup_result import EndpointInfo
from app.schemas.common import ErrorCode
from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from app.schemas.models import MAX_MODEL_ID
from app.services.execution_provider_catalog import ModelNotOnOpenRouterError
from app.services.openrouter_catalog import OpenRouterUnavailableError
from tests.api.model_helpers import FakeEndpointCatalog
from tests.db_helpers import Factory

MODELS = "/api/models"
UPTIME = Decimal("99.51388888888889")


def path(model_id: int | str) -> str:
    return f"{MODELS}/{model_id}/execution-providers"


@pytest.fixture
def endpoints(app: FastAPI) -> FakeEndpointCatalog:
    fake = FakeEndpointCatalog([])
    app.dependency_overrides[get_endpoint_catalog] = lambda: fake
    return fake


async def test_모델의_서버_업체를_OpenRouter_모델_ID로_물어_돌려준다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model(openrouter_model_id="mistralai/mistral-nemo")
    endpoints.endpoints = [
        EndpointInfo(provider_name="Io Net", status=0, uptime_last_1d=UPTIME),
        EndpointInfo(provider_name="DekaLLM"),
    ]

    response = await client.get(path(model["model_id"]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "items": [
            {
                "execution_provider": "Io Net",
                "status": 0,
                "uptime_last_1d": "99.51388888888889",
            },
            {"execution_provider": "DekaLLM", "status": None, "uptime_last_1d": None},
        ]
    }
    assert endpoints.asked == ["mistralai/mistral-nemo"]


async def test_업체가_없으면_빈_목록이다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()

    response = await client.get(path(model["model_id"]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"items": []}


async def test_모델_상태와_상관없이_조회할_수_있다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    for model_status in ("TESTING", "ACTIVE", "INACTIVE"):
        model = await factory.model(status=model_status)

        response = await client.get(path(model["model_id"]))

        assert response.status_code == status.HTTP_200_OK


async def test_등록되지_않은_모델은_404이고_OpenRouter에_묻지_않는다(
    client: AsyncClient, endpoints: FakeEndpointCatalog
) -> None:
    response = await client.get(path(MAX_MODEL_ID))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == ErrorCode.NOT_FOUND
    assert endpoints.asked == []


@pytest.mark.parametrize("model_id", ["0", "-1", "abc", str(MAX_MODEL_ID + 1)])
async def test_모델_번호가_올바르지_않으면_422다(
    client: AsyncClient, endpoints: FakeEndpointCatalog, model_id: str
) -> None:
    response = await client.get(path(model_id))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert endpoints.asked == []


async def test_OpenRouter가_모델을_모르면_전용_코드의_404다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.error = ModelNotOnOpenRouterError()

    response = await client.get(path(model["model_id"]))

    code = ModelErrorCode.OPENROUTER_MODEL_NOT_FOUND
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": code, "message": ERROR_SPECS[code].message}


async def test_업체_목록을_받지_못하면_502다(
    client: AsyncClient, factory: Factory, endpoints: FakeEndpointCatalog
) -> None:
    model = await factory.model()
    endpoints.error = OpenRouterUnavailableError()

    response = await client.get(path(model["model_id"]))

    code = ModelErrorCode.EXECUTION_PROVIDERS_UNAVAILABLE
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json() == {"code": code, "message": ERROR_SPECS[code].message}

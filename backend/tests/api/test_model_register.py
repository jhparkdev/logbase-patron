"""POST /api/models 테스트. OpenRouter에 있는 모델을 TESTING 상태로 등록한다."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.model_deps import get_openrouter_catalog
from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from app.schemas.model_register import (
    MAX_DISPLAY_NAME_LENGTH,
    MAX_OPENROUTER_MODEL_ID_LENGTH,
    MAX_PURPOSE_LENGTH,
)
from tests.api.model_helpers import FakeCatalog, info
from tests.api.test_auth import log_in, make_user
from tests.db_helpers import Factory

MODELS = "/api/models"
NEW_MODEL = "vendor/new"


@pytest.fixture
def catalog(app: FastAPI) -> FakeCatalog:
    fake = FakeCatalog([info(NEW_MODEL)])
    app.dependency_overrides[get_openrouter_catalog] = lambda: fake
    return fake


@pytest.fixture(autouse=True)
async def admin(client: AsyncClient, factory: Factory) -> int:
    """등록자로 기록되는 계정. 로그인한 계정이 기록되므로 이 계정으로 로그인해 둔다."""
    user = await make_user(factory)
    assert (await log_in(client, user["email"])).status_code == 200
    return int(user["user_id"])


def body(**overrides: Any) -> dict[str, Any]:
    return {"openrouter_model_id": NEW_MODEL, "display_name": "새 모델", **overrides}


async def test_등록하면_201과_상세와_같은_모양으로_돌려준다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [
        info(
            NEW_MODEL,
            name="Vendor: New",
            pricing={
                "prompt": Decimal("0.000001"),
                "completion": Decimal("0.000002"),
            },
            input_modalities=["text", "image"],
            output_modalities=["text"],
            context_length=1000,
            supported_parameters=["response_format", "tools"],
        )
    ]

    response = await client.post(MODELS, json=body(purpose="요약"))

    assert response.status_code == status.HTTP_201_CREATED
    created = response.json()
    assert created["openrouter_model_id"] == NEW_MODEL
    assert created["display_name"] == "새 모델"
    assert created["provider"] == "vendor"
    assert created["purpose"] == "요약"
    assert created["status"] == "TESTING"
    assert created["input_modalities"] == ["text", "image"]
    assert created["output_modalities"] == ["text"]
    assert created["supports_json_schema"] is True
    assert created["supports_tools"] is True
    assert created["context_length"] == 1000
    price = created["current_price"]
    assert Decimal(price["input_price_per_token"]) == Decimal("0.000001")
    assert Decimal(price["output_price_per_token"]) == Decimal("0.000002")
    assert created["last_test_status"] is None
    assert created["activated_at"] is None


async def test_등록한_모델은_목록과_상세에서_조회된다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    created = (await client.post(MODELS, json=body())).json()

    listed = (await client.get(MODELS)).json()["items"]
    detail = (await client.get(f"{MODELS}/{created['model_id']}")).json()

    assert [item["model_id"] for item in listed] == [created["model_id"]]
    assert detail == created


async def test_단가를_모르면_가격_미확인으로_등록된다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [info(NEW_MODEL, pricing={})]

    created = (await client.post(MODELS, json=body())).json()

    price = created["current_price"]
    assert price["price_status"] == "UNKNOWN"
    assert price["input_price_per_token"] is None
    assert price["output_price_per_token"] is None


async def test_앞뒤_공백은_지우고_비운_용도는_null로_저장한다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    payload = body(display_name="  새 모델  ", purpose="   ")

    created = (await client.post(MODELS, json=payload)).json()

    assert created["display_name"] == "새 모델"
    assert created["purpose"] is None


async def test_이미_등록된_모델은_409이다(
    client: AsyncClient, catalog: FakeCatalog, factory: Factory
) -> None:
    await factory.model(openrouter_model_id=NEW_MODEL, provider="vendor")

    response = await client.post(MODELS, json=body())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "code": ModelErrorCode.MODEL_ALREADY_REGISTERED,
        "message": ERROR_SPECS[ModelErrorCode.MODEL_ALREADY_REGISTERED].message,
    }


async def test_OpenRouter에_없는_모델은_422이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = [info("other/model")]

    response = await client.post(MODELS, json=body())

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json() == {
        "code": ModelErrorCode.MODEL_NOT_IN_OPENROUTER,
        "message": ERROR_SPECS[ModelErrorCode.MODEL_NOT_IN_OPENROUTER].message,
    }


async def test_OpenRouter에서_목록을_받지_못하면_502이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    catalog.models = None

    response = await client.post(MODELS, json=body())

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json()["code"] == ModelErrorCode.OPENROUTER_UNAVAILABLE


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"display_name": "이름만"},
        {"openrouter_model_id": NEW_MODEL},
        body(openrouter_model_id="no-slash"),
        body(openrouter_model_id="vendor/ new"),
        body(openrouter_model_id="vendor/"),
        body(openrouter_model_id="/model"),
        body(openrouter_model_id="vendor/a\x00b"),
        body(display_name="   "),
        body(display_name="a\x00b"),
        body(purpose="a\x00b"),
        body(status="ACTIVE"),
    ],
    ids=[
        "본문 없음",
        "모델 ID 없음",
        "표시 이름 없음",
        "슬래시 없는 모델 ID",
        "공백이 든 모델 ID",
        "이름 부분이 빈 모델 ID",
        "제공사 부분이 빈 모델 ID",
        "NUL 문자가 든 모델 ID",
        "공백뿐인 표시 이름",
        "NUL 문자가 든 표시 이름",
        "NUL 문자가 든 용도",
        "정해지지 않은 항목(상태)",
    ],
)
async def test_올바르지_않은_입력은_422이다(
    client: AsyncClient, catalog: FakeCatalog, payload: dict[str, Any]
) -> None:
    response = await client.post(MODELS, json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "length", "expected_status"),
    [
        ("openrouter_model_id", MAX_OPENROUTER_MODEL_ID_LENGTH, 201),
        ("openrouter_model_id", MAX_OPENROUTER_MODEL_ID_LENGTH + 1, 422),
        ("display_name", MAX_DISPLAY_NAME_LENGTH, 201),
        ("display_name", MAX_DISPLAY_NAME_LENGTH + 1, 422),
        ("purpose", MAX_PURPOSE_LENGTH, 201),
        ("purpose", MAX_PURPOSE_LENGTH + 1, 422),
    ],
)
async def test_글자_수의_경계(
    client: AsyncClient,
    catalog: FakeCatalog,
    field: str,
    length: int,
    expected_status: int,
) -> None:
    value = (
        "v/" + "x" * (length - 2) if field == "openrouter_model_id" else "x" * length
    )
    catalog.models = [info(value if field == "openrouter_model_id" else NEW_MODEL)]

    response = await client.post(MODELS, json=body(**{field: value}))

    assert response.status_code == expected_status


async def test_활성_계정이_없으면_401이다(
    client: AsyncClient, catalog: FakeCatalog, db_session: AsyncSession
) -> None:
    await db_session.execute(text("UPDATE users SET is_active = false"))

    response = await client.post(MODELS, json=body())

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_허용하지_않은_Origin의_등록_요청은_403이다(
    client: AsyncClient, catalog: FakeCatalog
) -> None:
    response = await client.post(
        MODELS, json=body(), headers={"Origin": "https://evil.test"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN

"""PATCH /api/models/{id}(표시 이름·용도 수정)와 PATCH /api/models/{id}/status(상태 변경) 테스트."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from app.schemas.model_register import MAX_DISPLAY_NAME_LENGTH, MAX_PURPOSE_LENGTH
from app.schemas.models import MAX_MODEL_ID
from tests.db_helpers import T0, Factory

MODELS = "/api/models"


@pytest.fixture(autouse=True)
async def admin(factory: Factory) -> int:
    """변경자로 기록되는 첫 활성 계정(DevUserDep)."""
    return (await factory.user())["user_id"]


def url(model_id: object) -> str:
    return f"{MODELS}/{model_id}"


def status_url(model_id: object) -> str:
    return f"{MODELS}/{model_id}/status"


# ---------------------------------------------------------------
# 표시 이름·용도 수정
# ---------------------------------------------------------------
async def test_표시_이름과_용도를_바꾸고_상세_모양으로_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(display_name="옛 이름", purpose="옛 용도")
    payload = {"display_name": "새 이름", "purpose": "새 용도"}

    response = await client.patch(url(model["model_id"]), json=payload)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert (body["display_name"], body["purpose"]) == ("새 이름", "새 용도")
    assert (await client.get(url(model["model_id"]))).json() == body


async def test_보낸_항목만_바꾸고_나머지는_그대로_둔다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(display_name="옛 이름", purpose="옛 용도")

    response = await client.patch(url(model["model_id"]), json={"purpose": "새 용도"})

    body = response.json()
    assert (body["display_name"], body["purpose"]) == ("옛 이름", "새 용도")


@pytest.mark.parametrize("value", [None, "", "   "], ids=["null", "빈 글자", "공백"])
async def test_용도를_null이나_빈_글자로_보내면_비운다(
    client: AsyncClient, factory: Factory, value: str | None
) -> None:
    model = await factory.model(purpose="옛 용도")

    response = await client.patch(url(model["model_id"]), json={"purpose": value})

    assert response.json()["purpose"] is None


async def test_표시_이름의_앞뒤_공백은_지운다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()

    response = await client.patch(
        url(model["model_id"]), json={"display_name": "  새 이름  "}
    )

    assert response.json()["display_name"] == "새 이름"


async def test_빈_본문은_아무것도_바꾸지_않는다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(display_name="이름", purpose="용도")

    response = await client.patch(url(model["model_id"]), json={})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert (body["display_name"], body["purpose"]) == ("이름", "용도")


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": None},
        {"display_name": "   "},
        {"display_name": "a\x00b"},
        {"purpose": "a\x00b"},
        {"openrouter_model_id": "other/model"},
        {"provider": "other"},
        {"status": "ACTIVE"},
    ],
    ids=[
        "표시 이름 null",
        "공백뿐인 표시 이름",
        "NUL 문자가 든 표시 이름",
        "NUL 문자가 든 용도",
        "모델 ID는 수정 불가",
        "제공사는 수정 불가",
        "상태는 이 경로로 수정 불가",
    ],
)
async def test_올바르지_않은_수정_입력은_422이다(
    client: AsyncClient, factory: Factory, payload: dict[str, Any]
) -> None:
    model = await factory.model()

    response = await client.patch(url(model["model_id"]), json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "length", "expected_status"),
    [
        ("display_name", MAX_DISPLAY_NAME_LENGTH, 200),
        ("display_name", MAX_DISPLAY_NAME_LENGTH + 1, 422),
        ("purpose", MAX_PURPOSE_LENGTH, 200),
        ("purpose", MAX_PURPOSE_LENGTH + 1, 422),
    ],
)
async def test_수정_글자_수의_경계(
    client: AsyncClient,
    factory: Factory,
    field: str,
    length: int,
    expected_status: int,
) -> None:
    model = await factory.model()

    response = await client.patch(url(model["model_id"]), json={field: "x" * length})

    assert response.status_code == expected_status


async def test_없는_모델은_수정할_수_없다(client: AsyncClient) -> None:
    response = await client.patch(url(999999), json={"purpose": "용도"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "모델을 찾을 수 없습니다.",
    }


@pytest.mark.parametrize(
    "model_id",
    ["abc", "0", "-1", str(MAX_MODEL_ID + 1)],
    ids=str,
)
async def test_올바르지_않은_모델_번호는_422이다(
    client: AsyncClient, model_id: str
) -> None:
    response = await client.patch(url(model_id), json={"purpose": "용도"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_활성_계정이_없으면_수정은_401이다(
    client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    model = await factory.model()
    await db_session.execute(text("UPDATE users SET is_active = false"))

    response = await client.patch(url(model["model_id"]), json={"purpose": "용도"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_허용하지_않은_Origin의_수정_요청은_403이다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()

    response = await client.patch(
        url(model["model_id"]),
        json={"purpose": "용도"},
        headers={"Origin": "https://evil.test"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------
# 상태 변경
# ---------------------------------------------------------------
async def test_최근_성공한_테스트가_있으면_사용_중으로_바꾸고_시각을_남긴다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(
        status="TESTING", last_success_test_at=T0 - timedelta(hours=1)
    )

    response = await client.patch(
        status_url(model["model_id"]), json={"status": "ACTIVE"}
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert datetime.fromisoformat(body["activated_at"]) == T0
    assert body["deactivated_at"] is None


async def test_사용_중에서_사용_중단으로_바꾸면_중단_시각을_남긴다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")

    response = await client.patch(
        status_url(model["model_id"]), json={"status": "INACTIVE"}
    )

    body = response.json()
    assert body["status"] == "INACTIVE"
    assert datetime.fromisoformat(body["deactivated_at"]) == T0


@pytest.mark.parametrize(
    ("elapsed", "expected_status"),
    [
        (timedelta(hours=24), 200),
        (timedelta(hours=24, seconds=1), 409),
    ],
    ids=["정확히 24시간", "24시간 1초"],
)
async def test_성공한_테스트가_24시간_이내인지_경계를_지킨다(
    client: AsyncClient, factory: Factory, elapsed: timedelta, expected_status: int
) -> None:
    model = await factory.model(status="TESTING", last_success_test_at=T0 - elapsed)

    response = await client.patch(
        status_url(model["model_id"]), json={"status": "ACTIVE"}
    )

    assert response.status_code == expected_status


async def test_성공한_테스트가_없으면_409이고_상태는_그대로이다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(status="TESTING")

    response = await client.patch(
        status_url(model["model_id"]), json={"status": "ACTIVE"}
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {
        "code": ModelErrorCode.TEST_NOT_PASSED,
        "message": ERROR_SPECS[ModelErrorCode.TEST_NOT_PASSED].message,
    }
    assert (await client.get(url(model["model_id"]))).json()["status"] == "TESTING"


@pytest.mark.parametrize(
    ("current", "target"),
    [("ACTIVE", "TESTING"), ("INACTIVE", "TESTING"), ("ACTIVE", "ACTIVE")],
)
async def test_허용하지_않는_전이는_409이다(
    client: AsyncClient, factory: Factory, current: str, target: str
) -> None:
    model = await factory.model(
        status=current, last_success_test_at=T0 - timedelta(hours=1)
    )

    response = await client.patch(
        status_url(model["model_id"]), json={"status": target}
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == ModelErrorCode.INVALID_STATUS_TRANSITION


@pytest.mark.parametrize(
    "payload",
    [{"status": "DELETED"}, {}, {"status": "ACTIVE", "display_name": "이름"}],
    ids=["없는 상태 값", "상태 없음", "정해지지 않은 항목"],
)
async def test_올바르지_않은_상태_입력은_422이다(
    client: AsyncClient, factory: Factory, payload: dict[str, Any]
) -> None:
    model = await factory.model()

    response = await client.patch(status_url(model["model_id"]), json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_없는_모델의_상태_변경은_404이다(client: AsyncClient) -> None:
    response = await client.patch(status_url(999999), json={"status": "INACTIVE"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"

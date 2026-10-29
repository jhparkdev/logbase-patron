"""app/api/errors.py 테스트. 모든 오류가 {code, message} 형식으로 나가고 내부 값을 드러내지 않는지 확인한다.

실제 라우트에 기대지 않도록 오류 처리기만 설치한 작은 앱으로 검사한다.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from app.api.errors import ApiError, install_error_handlers
from app.schemas.common import ErrorCode

# 응답에 그대로 나오면 안 되는 값들
SUBMITTED_SECRET = "secret-input-value"
INTERNAL_DETAIL = "internal failure detail"
CUSTOM_MESSAGE = "찾는 항목이 없습니다."


class ItemCreate(BaseModel):
    name: str = Field(max_length=3)


def build_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/items")
    async def create_item(item: ItemCreate) -> ItemCreate:
        return item

    @app.get("/missing")
    async def read_missing() -> None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, CUSTOM_MESSAGE)

    @app.get("/boom")
    async def explode() -> None:
        raise RuntimeError(INTERNAL_DETAIL)

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # 처리되지 않은 예외도 응답(500)으로 받아 보려고 앱 예외를 테스트로 다시 던지지 않게 한다.
    transport = ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client


async def test_api_error_uses_given_status_code_and_message(
    client: AsyncClient,
) -> None:
    response = await client.get("/missing")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": "NOT_FOUND", "message": CUSTOM_MESSAGE}


async def test_validation_error_does_not_echo_input(client: AsyncClient) -> None:
    """기본 422 응답은 입력값을 그대로 돌려준다. 비밀번호 같은 값이 응답에 남지 않아야 한다."""
    response = await client.post("/items", json={"name": SUBMITTED_SECRET})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert SUBMITTED_SECRET not in response.text


async def test_malformed_json_is_validation_error(client: AsyncClient) -> None:
    response = await client.post(
        "/items", content=b"{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_unknown_path_is_not_found(client: AsyncClient) -> None:
    response = await client.get("/no-such-path")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"


async def test_wrong_method_keeps_allow_header(client: AsyncClient) -> None:
    response = await client.delete("/items")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json()["code"] == "METHOD_NOT_ALLOWED"
    assert response.headers["allow"] == "POST"


async def test_unhandled_error_hides_internal_detail(client: AsyncClient) -> None:
    response = await client.get("/boom")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert INTERNAL_DETAIL not in response.text

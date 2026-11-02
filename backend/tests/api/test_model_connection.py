"""POST /api/models/{id}/test 테스트. 연결 테스트를 실행하고 결과를 돌려준다."""

from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.model_deps import get_connection_caller
from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.result import CallStatus
from app.schemas.model_error import ERROR_SPECS, ModelErrorCode
from app.schemas.model_test import MAX_TEST_PROMPT_LENGTH
from app.services.model_test import DEFAULT_PROMPT
from tests.connection_helpers import LATENCY, MODEL_ID, FakeCaller, failure, success
from tests.db_helpers import T0, Factory

MODELS = "/api/models"


@pytest.fixture
async def model_id(factory: Factory) -> int:
    """연결 테스트를 받을 수 있는 DB(PoC 프로젝트·Key, 연결 테스트 서비스, 관리자)와 모델."""
    project = await factory.project(project_code="PRJ-PATRON-POC", project_type="POC")
    await factory.service(service_code="PATRON_MODEL_TEST", service_type="PATRON")
    await factory.api_key(
        project_id=project["project_id"], secret_ref="OPENROUTER_KEY_POC"
    )
    await factory.user()
    model = await factory.model(
        openrouter_model_id=MODEL_ID, provider="vendor", status="TESTING"
    )
    return model["model_id"]


@pytest.fixture
def caller(app: FastAPI) -> FakeCaller:
    fake = FakeCaller(success())
    app.dependency_overrides[get_connection_caller] = lambda: fake
    return fake


def connection_url(model_id: object) -> str:
    return f"{MODELS}/{model_id}/test"


async def test_성공하면_200과_화면에_보일_값을_돌려준다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    response = await client.post(
        connection_url(model_id), json={"prompt": "테스트 문장"}
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert datetime.fromisoformat(body["tested_at"]) == T0 + LATENCY
    assert body["latency_ms"] == 850
    assert body["input_tokens"] == 18
    assert body["output_tokens"] == 2
    assert body["cost_usd"] == "0.000001"
    assert body["cost_status"] == "CONFIRMED"
    assert body["actual_provider"] == "Io Net"
    assert body["error_type"] is None
    assert body["error_message"] is None


async def test_실패해도_200이고_오류_종류와_문구를_돌려준다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    caller.result = failure(CallStatus.FAILED, ErrorType.AUTH_ERROR)

    response = await client.post(connection_url(model_id), json={})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["error_type"] == "AUTH_ERROR"
    assert body["error_message"] == USER_MESSAGES[ErrorType.AUTH_ERROR]
    assert body["cost_usd"] is None
    assert body["cost_status"] == "UNKNOWN"
    assert body["input_tokens"] is None


async def test_시간_초과도_200이고_TIMEOUT으로_돌려준다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    caller.result = failure(CallStatus.TIMEOUT, ErrorType.TIMEOUT_ERROR)

    body = (await client.post(connection_url(model_id), json={})).json()

    assert body["status"] == "TIMEOUT"
    assert body["error_type"] == "TIMEOUT_ERROR"


async def test_테스트_뒤_상세에_마지막_테스트_정보가_반영된다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    await client.post(connection_url(model_id), json={})

    detail = (await client.get(f"{MODELS}/{model_id}")).json()

    assert detail["last_test_status"] == "SUCCESS"
    assert datetime.fromisoformat(detail["last_test_at"]) == T0 + LATENCY
    assert datetime.fromisoformat(detail["last_success_test_at"]) == T0 + LATENCY


async def test_성공한_테스트_뒤에는_사용_중으로_바꿀_수_있다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    before = await client.patch(
        f"{MODELS}/{model_id}/status", json={"status": "ACTIVE"}
    )
    await client.post(connection_url(model_id), json={})
    after = await client.patch(f"{MODELS}/{model_id}/status", json={"status": "ACTIVE"})

    assert before.status_code == status.HTTP_409_CONFLICT
    assert before.json()["code"] == ModelErrorCode.TEST_NOT_PASSED
    assert after.status_code == status.HTTP_200_OK
    assert after.json()["status"] == "ACTIVE"


async def test_실패한_테스트_뒤에는_사용_중으로_바꿀_수_없다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    caller.result = failure(CallStatus.FAILED, ErrorType.PROVIDER_ERROR)
    await client.post(connection_url(model_id), json={})

    response = await client.patch(
        f"{MODELS}/{model_id}/status", json={"status": "ACTIVE"}
    )

    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"prompt": "내 문장"}, "내 문장"),
        ({"prompt": "  내 문장  "}, "내 문장"),
        ({}, DEFAULT_PROMPT),
        ({"prompt": None}, DEFAULT_PROMPT),
        ({"prompt": "   "}, DEFAULT_PROMPT),
    ],
    ids=["입력한 문장", "앞뒤 공백 제거", "본문 비어 있음", "null", "공백뿐"],
)
async def test_입력한_문장을_쓰고_비면_기본_문장을_쓴다(
    client: AsyncClient,
    model_id: int,
    caller: FakeCaller,
    payload: dict[str, Any],
    expected: str,
) -> None:
    await client.post(connection_url(model_id), json=payload)

    assert caller.calls[0]["messages"] == [{"role": "user", "content": expected}]


@pytest.mark.parametrize(
    ("length", "expected_status"),
    [
        (MAX_TEST_PROMPT_LENGTH, 200),
        (MAX_TEST_PROMPT_LENGTH + 1, 422),
    ],
)
async def test_문장_글자_수의_경계(
    client: AsyncClient,
    model_id: int,
    caller: FakeCaller,
    length: int,
    expected_status: int,
) -> None:
    response = await client.post(
        connection_url(model_id), json={"prompt": "x" * length}
    )

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "payload",
    [{"prompt": "a\x00b"}, {"prompt": 123}, {"status": "ACTIVE"}],
    ids=["NUL 문자", "글자가 아닌 값", "정해지지 않은 항목"],
)
async def test_올바르지_않은_입력은_422이고_호출하지_않는다(
    client: AsyncClient, model_id: int, caller: FakeCaller, payload: dict[str, Any]
) -> None:
    response = await client.post(connection_url(model_id), json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert caller.calls == []


async def test_없는_모델은_404이고_호출하지_않는다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    response = await client.post(connection_url(999999), json={})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"
    assert caller.calls == []


async def test_OpenRouter_Key가_없으면_503이다(
    client: AsyncClient, model_id: int, app: FastAPI
) -> None:
    app.dependency_overrides[get_connection_caller] = lambda: None

    response = await client.post(connection_url(model_id), json={})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "code": ModelErrorCode.OPENROUTER_KEY_MISSING,
        "message": ERROR_SPECS[ModelErrorCode.OPENROUTER_KEY_MISSING].message,
    }


async def test_활성_계정이_없으면_연결_테스트는_401이다(
    client: AsyncClient, model_id: int, caller: FakeCaller, db_session: AsyncSession
) -> None:
    await db_session.execute(text("UPDATE users SET is_active = false"))

    response = await client.post(connection_url(model_id), json={})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert caller.calls == []


async def test_허용하지_않은_Origin의_연결_테스트는_403이다(
    client: AsyncClient, model_id: int, caller: FakeCaller
) -> None:
    response = await client.post(
        connection_url(model_id), json={}, headers={"Origin": "https://evil.test"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert caller.calls == []

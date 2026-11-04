"""POST /api/usage-records 테스트. 고객 서비스가 보내는 호출 기록의 인증, 저장, 거절을 본다."""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AIRequest
from tests.db_helpers import Factory

URL = "/api/usage-records"
# 테스트용 가짜 값. 실제 토큰이 아니다
TOKEN = "ingest-test-only-not-a-real-token"
HEADERS = {"X-Patron-Ingest-Token": TOKEN}
OCTOBER = {"start_date": "2026-10-01", "end_date": "2026-10-31"}


@pytest.fixture
def with_token(app: FastAPI) -> None:
    """서버에 수신 토큰이 설정된 상태로 만든다. 로컬 .env의 값과 관계없이 시험한다."""
    base = app.dependency_overrides[get_settings]()
    settings = base.model_copy(update={"ingest_token": SecretStr(TOKEN)})
    app.dependency_overrides[get_settings] = lambda: settings


async def customer_key(factory: Factory) -> dict[str, Any]:
    customer = await factory.customer()
    service = await factory.service(service_type="CUSTOMER_FACING")
    key = await factory.api_key(
        owner_type="CUSTOMER",
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
    )
    return {"key_id": key["key_id"], "customer_code": customer["customer_code"]}


def body(owner: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": str(uuid.uuid4()),
        **owner,
        "task_ref": "detail-page-1001",
        "task_type": "상세페이지 생성",
        "model": "openai/gpt-4o-mini",
        "requested_at": "2026-10-10T01:00:00Z",
        "completed_at": "2026-10-10T01:00:02Z",
        "status": "SUCCESS",
        "input_tokens": 120,
        "output_tokens": 30,
        "cost_usd": "0.000045",
    }
    payload.update(overrides)
    return payload


async def count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(AIRequest)) or 0


# 인증


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Patron-Ingest-Token": "wrong"}, {"X-Patron-Ingest-Token": ""}],
)
async def test_a_missing_or_wrong_token_is_rejected_and_nothing_is_saved(
    client: AsyncClient,
    factory: Factory,
    db_session: AsyncSession,
    with_token: None,
    headers: dict[str, str],
) -> None:
    owner = await customer_key(factory)

    response = await client.post(URL, json=body(owner), headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert await count(db_session) == 0


async def test_every_request_is_rejected_when_the_server_has_no_token(
    client: AsyncClient, factory: Factory
) -> None:
    owner = await customer_key(factory)

    response = await client.post(URL, json=body(owner), headers=HEADERS)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_a_login_session_does_not_replace_the_token(
    client: AsyncClient, factory: Factory, with_token: None
) -> None:
    """client 는 로그인한 상태다. 로그인했다고 토큰 없이 기록할 수는 없다."""
    owner = await customer_key(factory)

    response = await client.post(URL, json=body(owner))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_the_origin_header_is_not_checked(
    client: AsyncClient, factory: Factory, with_token: None
) -> None:
    owner = await customer_key(factory)

    response = await client.post(
        URL, json=body(owner), headers={**HEADERS, "Origin": "https://evil.example"}
    )

    assert response.status_code == status.HTTP_201_CREATED


# 저장


async def test_a_valid_record_is_created(
    client: AsyncClient, factory: Factory, db_session: AsyncSession, with_token: None
) -> None:
    owner = await customer_key(factory)
    payload = body(owner)

    response = await client.post(URL, json=payload, headers=HEADERS)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {"request_id": payload["request_id"], "stored": True}
    assert await count(db_session) == 1


async def test_sending_the_same_request_id_again_is_ok_and_stores_nothing_new(
    client: AsyncClient, factory: Factory, db_session: AsyncSession, with_token: None
) -> None:
    owner = await customer_key(factory)
    payload = body(owner)
    await client.post(URL, json=payload, headers=HEADERS)

    response = await client.post(URL, json=payload, headers=HEADERS)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"request_id": payload["request_id"], "stored": False}
    assert await count(db_session) == 1


async def test_the_response_does_not_echo_the_token_or_the_record(
    client: AsyncClient, factory: Factory, with_token: None
) -> None:
    owner = await customer_key(factory)

    response = await client.post(URL, json=body(owner), headers=HEADERS)

    assert TOKEN not in response.text
    assert "gpt-4o" not in response.text
    assert owner["customer_code"] not in response.text


# 거절


async def test_a_malformed_record_is_a_validation_error(
    client: AsyncClient, factory: Factory, db_session: AsyncSession, with_token: None
) -> None:
    owner = await customer_key(factory)

    response = await client.post(
        URL, json=body(owner, request_id="not-a-uuid"), headers=HEADERS
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert await count(db_session) == 0


async def test_an_unknown_key_is_rejected_with_a_fixed_message(
    client: AsyncClient, db_session: AsyncSession, with_token: None
) -> None:
    response = await client.post(
        URL,
        json=body({"key_id": 987654, "customer_code": "CUST-X"}),
        headers=HEADERS,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "987654" not in response.text
    assert await count(db_session) == 0


async def test_a_customer_code_that_does_not_match_the_key_is_rejected(
    client: AsyncClient, factory: Factory, db_session: AsyncSession, with_token: None
) -> None:
    owner = await customer_key(factory)
    other = await factory.customer()

    response = await client.post(
        URL,
        json=body({**owner, "customer_code": other["customer_code"]}),
        headers=HEADERS,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert other["customer_code"] not in response.text
    assert await count(db_session) == 0


async def test_a_generation_id_used_by_another_request_is_rejected(
    client: AsyncClient, factory: Factory, with_token: None
) -> None:
    owner = await customer_key(factory)
    await client.post(
        URL, json=body(owner, openrouter_generation_id="gen-1"), headers=HEADERS
    )

    response = await client.post(
        URL, json=body(owner, openrouter_generation_id="gen-1"), headers=HEADERS
    )

    assert response.status_code == status.HTTP_409_CONFLICT


# 고객 사용량 화면에 나오는 모양


async def test_success_failed_and_timeout_records_show_up_in_the_customer_usage_summary(
    client: AsyncClient, factory: Factory, with_token: None
) -> None:
    owner = await customer_key(factory)
    records = [
        body(owner, task_ref="task-1", cost_usd="1.25"),
        body(
            owner,
            task_ref="task-1",
            status="FAILED",
            error_type="PROVIDER_ERROR",
            http_status=502,
            cost_usd=None,
            input_tokens=None,
            output_tokens=None,
        ),
        body(
            owner,
            task_ref="task-2",
            status="TIMEOUT",
            completed_at=None,
            cost_usd=None,
            input_tokens=None,
            output_tokens=None,
        ),
    ]
    for record in records:
        response = await client.post(URL, json=record, headers=HEADERS)
        assert response.status_code == status.HTTP_201_CREATED

    response = await client.get("/api/usage/customers/summary", params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    summary = response.json()
    assert summary["task_count"] == 2
    assert summary["call_count"] == 3
    assert summary["success_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["timeout_count"] == 1
    assert summary["confirmed_cost_usd"] == "1.250000000000000000"
    # 실패·timeout 호출의 비용은 0이 아니라 미확인이다
    assert summary["unknown_cost_count"] == 2

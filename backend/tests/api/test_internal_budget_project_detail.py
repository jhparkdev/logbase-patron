"""GET·PUT /api/usage/internal/projects/{project_id} 테스트. 프로젝트 상세와 월 예산 저장을 확인한다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Budget
from tests.db_helpers import Factory
from tests.internal_budget_helpers import internal_call

BASE = "/api/usage/internal/projects"
OCTOBER = {"month": "2026-10"}


def budget_body(**values: Any) -> dict[str, Any]:
    return {"monthly_amount_usd": "10.50", "effective_from_month": "2026-10", **values}


# ---------------------------------------------------------------
# 상세
# ---------------------------------------------------------------
async def test_상세는_합계_예산_서비스_구독료를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    project_id = project["project_id"]
    await factory.budget(project_id=project_id, monthly_amount_usd=Decimal(100))
    await internal_call(factory, project_id=project_id, cost_usd=Decimal(60))
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1),
        amount=Decimal(30),
        project_id=project_id,
        tool_name="도구 가",
    )

    response = await client.get(f"{BASE}/{project_id}", params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["project_id"] == project_id
    assert body["project_name"] == "알파"
    assert body["month"] == "2026-10"
    assert body["call_count"] == 1
    assert Decimal(body["confirmed_cost_usd"]) == 60
    assert Decimal(body["subscription_usd"]) == 30
    assert body["budget"]["month"] == "2026-10"
    assert body["budget"]["effective_from_month"] == "2026-10"
    assert Decimal(body["budget"]["used_usd"]) == 90
    assert Decimal(body["budget"]["usage_pct"]) == 90
    assert body["budget"]["status"] == "WARNING"
    assert len(body["services"]) == 1
    assert Decimal(body["services"][0]["budget_share_pct"]) == 60
    assert body["subscriptions"][0]["tool_name"] == "도구 가"
    assert Decimal(body["subscriptions"][0]["amount_usd"]) == 30
    assert body["subscriptions"][0]["status"] == "ACTIVE"


async def test_상세의_금액은_문자열이고_작은_값도_지수_표기가_아니다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project()
    project_id = project["project_id"]
    await internal_call(factory, project_id=project_id, cost_usd=Decimal("0.00000003"))

    body = (await client.get(f"{BASE}/{project_id}", params=OCTOBER)).json()

    for amount in (body["confirmed_cost_usd"], body["budget"]["used_usd"]):
        assert isinstance(amount, str)
        assert "e" not in amount.lower()
        assert Decimal(amount) == Decimal("0.00000003")


async def test_예산이_없는_프로젝트의_예산_값은_null이고_미설정이다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project()

    body = (await client.get(f"{BASE}/{project['project_id']}", params=OCTOBER)).json()

    assert body["budget"]["monthly_amount_usd"] is None
    assert body["budget"]["usage_pct"] is None
    assert body["budget"]["remaining_usd"] is None
    assert body["budget"]["status"] == "UNSET"


async def test_없는_프로젝트의_상세는_404이다(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/987654", params=OCTOBER)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("1", {}),
        ("1", {"month": "2026-13"}),
        ("1", {"month": "2026-10", "unknown_param": "1"}),
        ("0", OCTOBER),
        ("abc", OCTOBER),
    ],
    ids=["월 없음", "없는 월", "모르는 조건", "ID 0", "ID가 숫자 아님"],
)
async def test_잘못된_상세_조건은_422이다(
    client: AsyncClient, path: str, params: dict[str, str]
) -> None:
    response = await client.get(f"{BASE}/{path}", params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------
# 예산 저장
# ---------------------------------------------------------------
async def test_예산을_저장하면_상세에서_읽을_수_있다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project()
    project_id = project["project_id"]

    saved = await client.put(f"{BASE}/{project_id}/budget", json=budget_body())
    read = await client.get(f"{BASE}/{project_id}", params=OCTOBER)

    assert saved.status_code == status.HTTP_200_OK
    assert saved.json()["project_id"] == project_id
    assert saved.json()["effective_from_month"] == "2026-10"
    assert saved.json()["effective_to_month"] is None
    assert isinstance(saved.json()["monthly_amount_usd"], str)
    assert Decimal(saved.json()["monthly_amount_usd"]) == Decimal("10.50")
    assert Decimal(read.json()["budget"]["monthly_amount_usd"]) == Decimal("10.50")
    assert read.json()["budget"]["status"] == "NORMAL"


async def test_예산_저장은_첫_사용자_계정을_기록한다(
    client: AsyncClient, factory: Factory
) -> None:
    # 로그인 검사를 뒤로 미룬 팀 결정에 따라 시뮬레이터와 같은 임시 실행자를 쓴다
    user = await factory.user()
    project = await factory.project()

    await client.put(f"{BASE}/{project['project_id']}/budget", json=budget_body())

    created_by = await factory.session.scalar(
        select(Budget.created_by).where(Budget.project_id == project["project_id"])
    )
    assert created_by == user["user_id"]


async def test_기간이_겹치면_409와_문구를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project()
    path = f"{BASE}/{project['project_id']}/budget"
    await client.put(path, json=budget_body(effective_from_month="2026-10"))

    response = await client.put(path, json=budget_body(effective_from_month="2026-09"))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "BUDGET_PERIOD_CONFLICT"
    assert response.json()["message"]


async def test_없는_프로젝트의_예산_저장은_404이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.put(f"{BASE}/987654/budget", json=budget_body())

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize("amount", ["0", "-1", 10.5, "NaN", "1000000000000"])
async def test_잘못된_예산_금액은_422이다(
    client: AsyncClient, factory: Factory, amount: object
) -> None:
    await factory.user()
    project = await factory.project()

    response = await client.put(
        f"{BASE}/{project['project_id']}/budget",
        json=budget_body(monthly_amount_usd=amount),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    "body",
    [
        {"effective_from_month": "2026-10"},
        {"monthly_amount_usd": "10"},
        {"monthly_amount_usd": "10", "effective_from_month": "2026-10-01"},
        {**budget_body(), "unknown_field": 1},
    ],
    ids=["금액 없음", "시작 월 없음", "일까지 있음", "모르는 필드"],
)
async def test_잘못된_예산_본문은_422이다(
    client: AsyncClient, factory: Factory, body: dict[str, Any]
) -> None:
    await factory.user()
    project = await factory.project()

    response = await client.put(f"{BASE}/{project['project_id']}/budget", json=body)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_허용하지_않는_Origin의_예산_저장은_거절한다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project()

    response = await client.put(
        f"{BASE}/{project['project_id']}/budget",
        json=budget_body(),
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"

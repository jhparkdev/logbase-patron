"""GET /api/usage/internal/summary 테스트. 내부 AI 예산 관리(P-02)의 비용 요약 카드를 확인한다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.db_helpers import Factory
from tests.internal_budget_helpers import UNKNOWN_COST, internal_call

SUMMARY = "/api/usage/internal/summary"
OCTOBER = {"start_date": "2026-10-01", "end_date": "2026-10-31"}


async def test_요약은_확정_추정_구독료와_총_관리_비용을_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    price = await factory.model_price()
    await internal_call(factory, cost_usd=Decimal("1.5"))
    await internal_call(
        factory,
        cost_status="ESTIMATED",
        cost_usd=Decimal("0.5"),
        cost_source="PRICE_ESTIMATE",
        price_id=price["price_id"],
    )
    await internal_call(factory, **UNKNOWN_COST)
    await factory.subscription_cost(applied_month=date(2026, 10, 1), amount=Decimal(10))

    response = await client.get(SUMMARY, params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert Decimal(body["api_confirmed_usd"]) == Decimal("1.5")
    assert Decimal(body["api_estimated_usd"]) == Decimal("0.5")
    assert Decimal(body["subscription_usd"]) == Decimal(10)
    assert Decimal(body["total_managed_usd"]) == Decimal(12)
    assert body["unknown_cost_count"] == 1
    assert body["includes_estimate"] is True
    assert body["has_unknown"] is True


async def test_금액은_문자열이고_작은_값도_지수_표기가_아니다(
    client: AsyncClient, factory: Factory
) -> None:
    await internal_call(factory, cost_usd=Decimal("0.00000003"))

    body = (await client.get(SUMMARY, params=OCTOBER)).json()

    assert isinstance(body["api_confirmed_usd"], str)
    assert "e" not in body["api_confirmed_usd"].lower()
    assert Decimal(body["api_confirmed_usd"]) == Decimal("0.00000003")


async def test_호출이_없으면_0을_돌려주고_오류가_아니다(
    client: AsyncClient, factory: Factory
) -> None:
    response = await client.get(SUMMARY, params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert Decimal(body["total_managed_usd"]) == 0
    assert body["includes_estimate"] is False
    assert body["has_unknown"] is False


async def test_기간을_보내지_않으면_최근_30일을_조회한다(
    client: AsyncClient, factory: Factory
) -> None:
    response = await client.get(SUMMARY)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    ("start_date", "expected_status"),
    [
        ("2025-12-31", status.HTTP_200_OK),
        ("2025-12-30", status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
    ids=["366일", "367일"],
)
async def test_조회_기간은_366일까지다(
    client: AsyncClient, factory: Factory, start_date: str, expected_status: int
) -> None:
    params = {"start_date": start_date, "end_date": "2026-12-31"}

    response = await client.get(SUMMARY, params=params)

    assert response.status_code == expected_status
    if expected_status != status.HTTP_200_OK:
        assert response.json()["code"] == "INVALID_PERIOD"


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2026-10-01"},
        {"start_date": "2026-10-31", "end_date": "2026-10-01"},
    ],
    ids=["시작일만 있음", "시작일이 종료일보다 늦음"],
)
async def test_잘못된_기간은_INVALID_PERIOD로_거절한다(
    client: AsyncClient, factory: Factory, params: dict[str, str]
) -> None:
    response = await client.get(SUMMARY, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "INVALID_PERIOD"


@pytest.mark.parametrize(
    "params",
    [
        {"unknown_param": "1"},
        {"start_date": "2026-13-01", "end_date": "2026-10-31"},
        {"start_date": "not-a-date", "end_date": "2026-10-31"},
    ],
    ids=["모르는 조건", "없는 날짜", "날짜 형식 아님"],
)
async def test_허용하지_않는_조건은_422이다(
    client: AsyncClient, factory: Factory, params: dict[str, Any]
) -> None:
    response = await client.get(SUMMARY, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"

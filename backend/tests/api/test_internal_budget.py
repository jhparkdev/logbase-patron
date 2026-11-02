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
TREND = "/api/usage/internal/trend"
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


# ---------------------------------------------------------------
# 일별 추이
# ---------------------------------------------------------------
async def test_추이는_기간의_날짜_수만큼_돌려주고_호출이_없는_날은_0이다(
    client: AsyncClient, factory: Factory
) -> None:
    await internal_call(factory, cost_usd=Decimal("1.5"))
    params = {"start_date": "2026-10-08", "end_date": "2026-10-12"}

    response = await client.get(TREND, params=params)

    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert [item["date"] for item in items] == [
        "2026-10-08",
        "2026-10-09",
        "2026-10-10",
        "2026-10-11",
        "2026-10-12",
    ]
    assert [Decimal(item["api_confirmed_usd"]) for item in items] == [
        0,
        0,
        Decimal("1.5"),
        0,
        0,
    ]


async def test_추이의_금액도_지수_표기가_아닌_문자열이다(
    client: AsyncClient, factory: Factory
) -> None:
    await internal_call(factory, cost_usd=Decimal("0.00000003"))

    items = (await client.get(TREND, params=OCTOBER)).json()["items"]

    amount = next(
        item["api_confirmed_usd"] for item in items if item["date"] == "2026-10-10"
    )
    assert isinstance(amount, str)
    assert "e" not in amount.lower()
    assert Decimal(amount) == Decimal("0.00000003")


async def test_추이도_잘못된_기간은_INVALID_PERIOD로_거절한다(
    client: AsyncClient, factory: Factory
) -> None:
    params = {"start_date": "2026-10-31", "end_date": "2026-10-01"}

    response = await client.get(TREND, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "INVALID_PERIOD"


# ---------------------------------------------------------------
# 프로젝트·모델 조건
# ---------------------------------------------------------------
async def test_프로젝트를_고르면_요약이_그_프로젝트_기준이다(
    client: AsyncClient, factory: Factory
) -> None:
    mine = await factory.project()
    other = await factory.project()
    await internal_call(factory, project_id=mine["project_id"], cost_usd=Decimal(2))
    await internal_call(factory, project_id=other["project_id"], cost_usd=Decimal(5))
    month = date(2026, 10, 1)
    await factory.subscription_cost(
        applied_month=month, amount=Decimal(10), project_id=mine["project_id"]
    )
    await factory.subscription_cost(applied_month=month, amount=Decimal(40))
    params = {**OCTOBER, "project_id": mine["project_id"]}

    body = (await client.get(SUMMARY, params=params)).json()

    assert Decimal(body["api_confirmed_usd"]) == Decimal(2)
    assert Decimal(body["subscription_usd"]) == Decimal(10)
    assert Decimal(body["total_managed_usd"]) == Decimal(12)
    assert body["subscription_excluded"] is False


async def test_모델을_고르면_요약에서_구독료가_빠지고_제외_표시가_켜진다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()
    other = await factory.model()
    await internal_call(factory, model_id=model["model_id"], cost_usd=Decimal(2))
    await internal_call(factory, model_id=other["model_id"], cost_usd=Decimal(5))
    await factory.subscription_cost(applied_month=date(2026, 10, 1), amount=Decimal(10))
    params = {**OCTOBER, "model_id": model["model_id"]}

    body = (await client.get(SUMMARY, params=params)).json()

    assert Decimal(body["api_confirmed_usd"]) == Decimal(2)
    assert Decimal(body["subscription_usd"]) == 0
    assert body["subscription_excluded"] is True


async def test_조건이_없으면_제외_표시가_꺼져_있다(
    client: AsyncClient, factory: Factory
) -> None:
    body = (await client.get(SUMMARY, params=OCTOBER)).json()

    assert body["subscription_excluded"] is False


async def test_추이도_프로젝트와_모델_조건을_따른다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project()
    model = await factory.model()
    await internal_call(
        factory,
        project_id=project["project_id"],
        model_id=model["model_id"],
        cost_usd=Decimal(2),
    )
    await internal_call(factory, cost_usd=Decimal(5))
    params = {
        **OCTOBER,
        "project_id": project["project_id"],
        "model_id": model["model_id"],
    }

    body = (await client.get(TREND, params=params)).json()

    total = sum(Decimal(point["api_confirmed_usd"]) for point in body["items"])
    assert total == Decimal(2)


@pytest.mark.parametrize("endpoint", [SUMMARY, TREND], ids=["요약", "추이"])
@pytest.mark.parametrize(
    "params",
    [
        {"project_id": "0"},
        {"project_id": "abc"},
        {"model_id": "-1"},
        {"model_id": "abc"},
    ],
    ids=[
        "프로젝트 ID 0",
        "프로젝트 ID가 숫자 아님",
        "모델 ID 음수",
        "모델 ID가 숫자 아님",
    ],
)
async def test_잘못된_프로젝트_모델_번호는_422이다(
    client: AsyncClient, endpoint: str, params: dict[str, str]
) -> None:
    response = await client.get(endpoint, params={**OCTOBER, **params})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"

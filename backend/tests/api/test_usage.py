"""고객 AI 사용 현황(P-01) API 테스트. 집계 값 자체는 tests/services/test_aggregation.py가 검증한다."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Budget
from app.services.budget_policy import WARNING_PCT
from tests.api.test_auth import log_in, make_user
from tests.db_helpers import Factory

# 로그인한 사용자만 부를 수 있는 API다. 로그인 경계는 tests/test_main.py 에서 확인한다
pytestmark = pytest.mark.usefixtures("signed_in")

BASE = "/api/usage/customers"
OCTOBER = {"start_date": "2026-10-01", "end_date": "2026-10-31"}
IN_OCTOBER = datetime(2026, 10, 10, tzinfo=UTC)


async def customer_call(factory: Factory, **values: Any) -> None:
    await factory.ai_request(
        **{"usage_origin": "CUSTOMER_SERVICE", "requested_at": IN_OCTOBER, **values}
    )


def budget_body(**values: Any) -> dict[str, Any]:
    return {"monthly_amount_usd": "10.50", "effective_from_month": "2026-10", **values}


async def test_summary_sends_money_as_strings(
    client: AsyncClient, factory: Factory
) -> None:
    await customer_call(factory, cost_status="CONFIRMED", cost_usd=Decimal("1.25"))
    await customer_call(factory, status="TIMEOUT", error_type="TIMEOUT_ERROR")

    response = await client.get(f"{BASE}/summary", params=OCTOBER)

    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["confirmed_cost_usd"]) == Decimal("1.25")
    assert isinstance(body["confirmed_cost_usd"], str)
    assert body["unknown_cost_count"] == 1
    assert body["comparison_end_date"] == "2026-09-30"


async def test_default_period_is_the_last_30_kst_days(client: AsyncClient) -> None:
    # 고정 시각 T0는 KST 10월 1일이다
    response = await client.get(f"{BASE}/trend")

    items = response.json()["items"]
    assert len(items) == 30
    assert items[0]["date"] == "2026-09-02"
    assert items[-1]["date"] == "2026-10-01"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-01-01", "2027-01-01", 200),  # 366일
        ("2026-01-01", "2027-01-02", 422),  # 367일
        ("2026-01-01", "2026-12-31", 200),  # 365일
        ("2026-10-02", "2026-10-01", 422),  # 시작 > 종료
    ],
)
@pytest.mark.parametrize("path", ["summary", "trend", "rows", "requests"])
async def test_period_rules_apply_to_every_block(
    client: AsyncClient, path: str, start: str, end: str, expected: int
) -> None:
    response = await client.get(
        f"{BASE}/{path}", params={"start_date": start, "end_date": end}
    )

    assert response.status_code == expected
    if expected == 422:
        assert response.json()["code"] == "INVALID_PERIOD"


async def test_only_one_period_date_is_rejected(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/summary", params={"start_date": "2026-10-01"})

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_PERIOD"


@pytest.mark.parametrize("path", ["rows", "requests"])
async def test_sort_values_outside_the_list_are_rejected_without_echoing_input(
    client: AsyncClient, path: str
) -> None:
    response = await client.get(
        f"{BASE}/{path}", params={**OCTOBER, "sort": "password_hash"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "password_hash" not in response.text


async def test_rows_and_requests_return_pages(
    client: AsyncClient, factory: Factory
) -> None:
    customer = await factory.customer(name="고객 가")
    service = await factory.service(name="AI PDP")
    for _ in range(3):
        await customer_call(
            factory,
            customer_id=customer["customer_id"],
            service_id=service["service_id"],
        )

    rows = await client.get(f"{BASE}/rows", params=OCTOBER)
    requests = await client.get(
        f"{BASE}/requests", params={**OCTOBER, "page": 2, "page_size": 2}
    )

    assert rows.json()["items"][0]["customer_name"] == "고객 가"
    assert rows.json()["items"][0]["budget"]["status"] == "UNSET"
    assert rows.json()["items"][0]["budget"]["usage_pct"] is None
    assert requests.json()["total"] == 3
    assert requests.json()["page"] == 2
    assert len(requests.json()["items"]) == 1


async def test_options_are_listed(client: AsyncClient, factory: Factory) -> None:
    customer = await factory.customer(name="고객 가")

    response = await client.get(f"{BASE}/options")

    assert {"id": customer["customer_id"], "name": "고객 가"} in response.json()[
        "customers"
    ]


async def test_detail_returns_budget_and_services(
    client: AsyncClient, factory: Factory
) -> None:
    customer = await factory.customer(name="고객 가")
    service = await factory.service(name="AI PDP")
    await factory.budget(
        scope_type="CUSTOMER",
        customer_id=customer["customer_id"],
        monthly_amount_usd=Decimal(10),
    )
    await customer_call(
        factory,
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
        cost_status="CONFIRMED",
        cost_usd=Decimal(2),
    )

    response = await client.get(
        f"{BASE}/{customer['customer_id']}", params={"month": "2026-10"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-10"
    assert body["budget"]["effective_from_month"] == "2026-10"
    assert body["budget"]["status"] == "NORMAL"
    assert Decimal(body["services"][0]["budget_share_pct"]) == Decimal(20)


async def test_detail_sends_threshold_and_service_total_as_strings(
    client: AsyncClient, factory: Factory
) -> None:
    customer = await factory.customer()
    await customer_call(
        factory,
        customer_id=customer["customer_id"],
        cost_status="CONFIRMED",
        cost_usd=Decimal("1.25"),
    )

    response = await client.get(
        f"{BASE}/{customer['customer_id']}", params={"month": "2026-10"}
    )

    body = response.json()
    threshold = body["budget"]["warning_threshold_pct"]
    total = body["services"][0]["total_cost_usd"]
    assert isinstance(threshold, str)
    assert Decimal(threshold) == WARNING_PCT
    assert isinstance(total, str)
    assert Decimal(total) == Decimal("1.25")


async def test_detail_of_an_unknown_customer_is_404(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/987654", params={"month": "2026-10"})

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize("month", ["2026-13", "2026-10-01", ""])
async def test_detail_rejects_invalid_months(
    client: AsyncClient, factory: Factory, month: str
) -> None:
    customer = await factory.customer()

    response = await client.get(
        f"{BASE}/{customer['customer_id']}", params={"month": month}
    )

    assert response.status_code == 422


async def test_budget_can_be_saved_and_then_read(
    client: AsyncClient, factory: Factory
) -> None:
    customer = await factory.customer()
    await factory.user()

    saved = await client.put(
        f"{BASE}/{customer['customer_id']}/budget", json=budget_body()
    )
    read = await client.get(
        f"{BASE}/{customer['customer_id']}", params={"month": "2026-10"}
    )

    assert saved.status_code == 200
    assert saved.json()["effective_from_month"] == "2026-10"
    assert saved.json()["effective_to_month"] is None
    assert Decimal(saved.json()["monthly_amount_usd"]) == Decimal("10.50")
    assert Decimal(read.json()["budget"]["monthly_amount_usd"]) == Decimal("10.50")


async def test_saving_a_budget_records_the_signed_in_account(
    client: AsyncClient, factory: Factory
) -> None:
    # 먼저 만든 계정(signed_in)이 아니라 지금 로그인한 계정이 기록돼야 한다
    user = await make_user(factory)
    assert (await log_in(client, user["email"])).status_code == 200
    customer = await factory.customer()

    await client.put(f"{BASE}/{customer['customer_id']}/budget", json=budget_body())

    created_by = await factory.session.scalar(
        select(Budget.created_by).where(Budget.customer_id == customer["customer_id"])
    )
    assert created_by == user["user_id"]


async def test_budget_overlap_returns_a_conflict_with_a_message(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    customer = await factory.customer()
    path = f"{BASE}/{customer['customer_id']}/budget"
    await client.put(path, json=budget_body(effective_from_month="2026-10"))

    response = await client.put(path, json=budget_body(effective_from_month="2026-09"))

    assert response.status_code == 409
    assert response.json()["code"] == "BUDGET_PERIOD_CONFLICT"
    assert response.json()["message"]


async def test_budget_for_an_unknown_customer_is_404(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.put(f"{BASE}/987654/budget", json=budget_body())

    assert response.status_code == 404


@pytest.mark.parametrize("amount", ["0", "-1", 10.5, "NaN"])
async def test_invalid_budget_amount_is_rejected(
    client: AsyncClient, factory: Factory, amount: object
) -> None:
    await factory.user()
    customer = await factory.customer()

    response = await client.put(
        f"{BASE}/{customer['customer_id']}/budget",
        json=budget_body(monthly_amount_usd=amount),
    )

    assert response.status_code == 422

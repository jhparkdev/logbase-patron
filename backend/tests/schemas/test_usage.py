"""P-01 요청·응답 모델의 검증 규칙 테스트."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import CostStatus, RequestStatus
from app.schemas.usage import (
    MAX_PAGE_SIZE,
    BudgetUsage,
    CustomerBudgetRead,
    CustomerBudgetSave,
    CustomerMonthQuery,
    CustomerRequestRow,
    CustomerRowSort,
    CustomerRowsQuery,
    CustomerServiceUsage,
    CustomerUsageDetail,
    CustomerUsageRow,
    RequestRowSort,
    RequestRowsQuery,
    UsageFilterQuery,
    UsageSummary,
    UsageTrendPoint,
)
from app.services.budget_policy import BudgetStatus


def budget_input(**values: Any) -> dict[str, Any]:
    return {"monthly_amount_usd": "10.5", "effective_from_month": "2026-10", **values}


def test_budget_amount_is_received_as_a_decimal_string() -> None:
    saved = CustomerBudgetSave.model_validate(budget_input())

    assert saved.monthly_amount_usd == Decimal("10.5")
    assert saved.effective_from_month == date(2026, 10, 1)


@pytest.mark.parametrize(
    "amount",
    [
        10.5,  # 숫자는 float을 거치므로 받지 않는다
        "0",
        "-1",
        "NaN",
        "Infinity",
        "1e3000",
        "abc",
        "1000000000000",  # NUMERIC(30,18)의 정수부 12자리를 넘는다
        "0.0000000000000000001",  # 소수 18자리를 넘는다
    ],
)
def test_invalid_budget_amounts_are_rejected(amount: object) -> None:
    with pytest.raises(ValidationError):
        CustomerBudgetSave.model_validate(budget_input(monthly_amount_usd=amount))


def test_largest_storable_budget_amount_is_accepted() -> None:
    amount = "999999999999.999999999999999999"

    saved = CustomerBudgetSave.model_validate(budget_input(monthly_amount_usd=amount))

    assert saved.monthly_amount_usd == Decimal(amount)


@pytest.mark.parametrize(
    "month",
    ["2026-13", "2026-00", "2026-1", "2026-10-01", "0000-01", "9999-12", 202610],
)
def test_invalid_months_are_rejected(month: object) -> None:
    with pytest.raises(ValidationError):
        CustomerBudgetSave.model_validate(budget_input(effective_from_month=month))


def test_month_is_written_back_as_year_and_month() -> None:
    query = CustomerMonthQuery.model_validate({"month": "2026-02"})

    assert query.model_dump(mode="json") == {"month": "2026-02"}


def test_money_is_serialized_as_a_string_and_unknown_cost_stays_null() -> None:
    row = CustomerRequestRow(
        request_id="00000000-0000-0000-0000-000000000001",
        requested_at="2026-10-01T00:00:00Z",
        customer_id=None,
        customer_name=None,
        service_id=1,
        service_name="서비스",
        model="vendor/model",
        task_id=None,
        task_type=None,
        task_type_label=None,
        tokens=None,
        cost_usd=None,
        cost_status=CostStatus.UNKNOWN,
        status=RequestStatus.TIMEOUT,
        error_type=None,
    )

    dumped = row.model_dump(mode="json")
    assert dumped["cost_usd"] is None

    priced = row.model_copy(update={"cost_usd": Decimal("0.0200")})
    assert priced.model_dump(mode="json")["cost_usd"] == "0.0200"


@pytest.mark.parametrize(
    ("stored", "sent"),
    [
        # DB NUMERIC(30,18)의 0원(청구 없음)은 Decimal('0E-18')로 읽힌다
        ("0E-18", "0.000000000000000000"),
        # 0.000001 미만도 str(Decimal)은 지수로 쓴다
        ("6.43000000000E-7", "0.000000643000000000"),
        ("0.031524000000000000", "0.031524000000000000"),
    ],
)
def test_call_cost_is_sent_in_plain_notation_without_rounding(
    stored: str, sent: str
) -> None:
    row = CustomerRequestRow(
        request_id="00000000-0000-0000-0000-000000000001",
        requested_at="2026-10-01T00:00:00Z",
        customer_id=1,
        customer_name="고객",
        service_id=1,
        service_name="서비스",
        model="vendor/model",
        task_id=None,
        task_type=None,
        task_type_label=None,
        tokens=10,
        cost_usd=Decimal(stored),
        cost_status=CostStatus.CONFIRMED,
        status=RequestStatus.FAILED,
        error_type=None,
    )

    dumped = row.model_dump(mode="json")["cost_usd"]

    assert dumped == sent
    assert Decimal(dumped) == Decimal(stored)


def _budget(zero: Decimal) -> BudgetUsage:
    return BudgetUsage(
        month=date(2026, 10, 1),
        monthly_amount_usd=zero,
        effective_from_month=date(2026, 10, 1),
        used_usd=zero,
        usage_pct=zero,
        confirmed_usage_pct=zero,
        remaining_usd=zero,
        unknown_cost_count=0,
        status=BudgetStatus.NORMAL,
        warning_threshold_pct=zero,
    )


def test_no_amount_or_rate_in_the_responses_is_sent_in_exponent_notation() -> None:
    zero = Decimal("0E-18")
    counts = {"task_count": 0, "call_count": 0, "unknown_cost_count": 0}
    costs = {"confirmed_cost_usd": zero, "estimated_cost_usd": zero}
    service = CustomerServiceUsage(
        service_id=1,
        service_name="서비스",
        total_cost_usd=zero,
        budget_share_pct=zero,
        **counts,
        **costs,
    )
    responses = [
        UsageSummary(
            comparison_start_date=date(2026, 9, 1),
            comparison_end_date=date(2026, 9, 30),
            success_count=0,
            failed_count=0,
            timeout_count=0,
            input_tokens=0,
            output_tokens=0,
            task_change_pct=zero,
            call_change_pct=zero,
            confirmed_cost_change_pct=zero,
            estimated_cost_change_pct=zero,
            **counts,
            **costs,
        ),
        UsageTrendPoint(date=date(2026, 10, 1), **counts, **costs),
        CustomerUsageRow(
            customer_id=1,
            customer_name="고객",
            service_id=1,
            service_name="서비스",
            budget=_budget(zero),
            **counts,
            **costs,
        ),
        CustomerUsageDetail(
            customer_id=1,
            customer_name="고객",
            month=date(2026, 10, 1),
            budget=_budget(zero),
            services=[service],
            **counts,
            **costs,
        ),
        CustomerBudgetRead(
            budget_id=1,
            customer_id=1,
            monthly_amount_usd=zero,
            effective_from_month=date(2026, 10, 1),
            effective_to_month=None,
        ),
    ]

    for response in responses:
        text = response.model_dump_json()
        assert "E-" not in text and "E+" not in text, type(response).__name__


def test_unknown_query_names_are_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageFilterQuery.model_validate({"from": "2026-10-01"})


@pytest.mark.parametrize("name", ["start_date", "end_date"])
@pytest.mark.parametrize("value", ["1999-12-31", "2101-01-01"])
def test_dates_outside_the_calendar_range_are_rejected(name: str, value: str) -> None:
    # 범위 밖 날짜는 이전 기간과 다음 날을 계산할 때 달력 범위를 벗어날 수 있다
    with pytest.raises(ValidationError):
        UsageFilterQuery.model_validate({name: value})


@pytest.mark.parametrize("name", ["customer_id", "service_id", "model_id"])
@pytest.mark.parametrize("value", [0, 2**63])
def test_filter_ids_must_fit_the_database_range(name: str, value: int) -> None:
    with pytest.raises(ValidationError):
        UsageFilterQuery.model_validate({name: value})


def test_sort_values_outside_the_allowed_list_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CustomerRowsQuery.model_validate({"sort": "password_hash"})
    with pytest.raises(ValidationError):
        RequestRowsQuery.model_validate({"sort": "password_hash"})


def test_default_sort_is_confirmed_cost_and_newest_call() -> None:
    assert CustomerRowsQuery().sort == CustomerRowSort.CONFIRMED
    assert RequestRowsQuery().sort == RequestRowSort.REQUESTED_AT


def test_default_page_size_matches_the_screen_and_has_a_limit() -> None:
    assert CustomerRowsQuery().page_size == 10
    with pytest.raises(ValidationError):
        CustomerRowsQuery(page_size=MAX_PAGE_SIZE + 1)

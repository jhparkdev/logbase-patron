"""P-01 요청·응답 모델의 검증 규칙 테스트."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import CostStatus, RequestStatus
from app.schemas.usage import (
    MAX_PAGE_SIZE,
    CustomerBudgetSave,
    CustomerMonthQuery,
    CustomerRequestRow,
    CustomerRowSort,
    CustomerRowsQuery,
    RequestRowSort,
    RequestRowsQuery,
    UsageFilterQuery,
)


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

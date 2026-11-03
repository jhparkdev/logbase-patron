"""app/mock_data/budgets.py 테스트: 월 예산과 구독료."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from app.mock_data import budgets, dataset
from app.mock_data.model_book import build_model_book
from app.mock_data.organizations import CUSTOMERS, project_id
from app.mock_data.period import KST
from app.mock_data.snapshot import load_snapshot
from app.mock_data.usage import generate_customer_usage
from app.models import BudgetScopeType, CostStatus
from app.services.budget_policy import BudgetStatus, evaluate_budget

SEPTEMBER = date(2026, 9, 1)
OCTOBER = date(2026, 10, 1)
NOVEMBER = date(2026, 11, 1)
CUSTOMER_IDS = {c.name: c.customer_id for c in CUSTOMERS}


@pytest.fixture(scope="module")
def monthly_usage() -> dict[tuple[int, date], tuple[Decimal, Decimal]]:
    usage = generate_customer_usage(build_model_book(load_snapshot()))
    totals: dict[tuple[int, date], list[Decimal]] = defaultdict(
        lambda: [Decimal(0), Decimal(0)]
    )
    for row in usage.requests:
        if row["customer_id"] is None or row["cost_usd"] is None:
            continue
        month = row["requested_at"].astimezone(KST).date().replace(day=1)
        index = 0 if row["cost_status"] == CostStatus.CONFIRMED else 1
        totals[(row["customer_id"], month)][index] += row["cost_usd"]
    return {key: (value[0], value[1]) for key, value in totals.items()}


def _status(monthly_usage: dict, customer: str, month: date) -> BudgetStatus:
    customer_id = CUSTOMER_IDS[customer]
    amount = budgets.monthly_amount(BudgetScopeType.CUSTOMER, customer_id, month)
    confirmed, estimated = monthly_usage.get(
        (customer_id, month), (Decimal(0), Decimal(0))
    )
    return evaluate_budget(amount, confirmed, estimated).status


@pytest.mark.parametrize(
    ("customer", "expected"),
    [
        ("로웰린 스튜디오", BudgetStatus.OVER),
        ("뮤렌 코스메틱", BudgetStatus.WARNING),
        ("에이븐전자몰", BudgetStatus.NORMAL),
        ("솔레담 푸드", BudgetStatus.NORMAL),
        ("모뉴하우스", BudgetStatus.UNSET),
    ],
)
def test_october_shows_every_budget_status(
    monthly_usage: dict, customer: str, expected: BudgetStatus
) -> None:
    assert _status(monthly_usage, customer, OCTOBER) == expected


def test_over_budget_customer_got_a_larger_budget_from_november(
    monthly_usage: dict,
) -> None:
    customer_id = CUSTOMER_IDS["로웰린 스튜디오"]
    october = budgets.monthly_amount(BudgetScopeType.CUSTOMER, customer_id, OCTOBER)
    november = budgets.monthly_amount(BudgetScopeType.CUSTOMER, customer_id, NOVEMBER)

    assert october is not None and november is not None and november > october
    assert _status(monthly_usage, "로웰린 스튜디오", NOVEMBER) == BudgetStatus.NORMAL


def test_budget_periods_of_the_same_target_never_overlap() -> None:
    # ex_budgets_no_overlap 제약과 같은 규칙(종료 월 포함, 종료 NULL = 무기한)
    by_target: dict[tuple, list] = defaultdict(list)
    for budget in budgets.BUDGETS:
        by_target[(budget.scope_type, budget.owner_id)].append(budget)
    for periods in by_target.values():
        periods.sort(key=lambda b: b.effective_from_month)
        for earlier, later in pairwise(periods):
            assert earlier.effective_to_month is not None
            assert earlier.effective_to_month < later.effective_from_month


def test_budget_rows_follow_the_table_rules() -> None:
    for row in budgets.budget_rows():
        assert row["monthly_amount_usd"] > 0
        assert row["effective_from_month"].day == 1
        to_month = row["effective_to_month"]
        assert to_month is None or (
            to_month.day == 1 and to_month >= row["effective_from_month"]
        )
        if row["scope_type"] == BudgetScopeType.CUSTOMER:
            assert row["customer_id"] is not None and row["project_id"] is None
        else:
            assert row["project_id"] is not None and row["customer_id"] is None


def test_subscriptions_are_monthly_usd_and_unique_per_month() -> None:
    rows = budgets.subscription_rows()
    keys = [(row["subscription_reference"], row["applied_month"]) for row in rows]

    assert len(set(keys)) == len(keys)
    for row in rows:
        assert row["currency"] == "USD"
        assert row["applied_month"].day == 1
        assert row["amount"] >= 0


@pytest.fixture(scope="module")
def project_usage() -> dict[tuple[int, date], tuple[Decimal, Decimal]]:
    data = dataset.build_dataset()
    totals: dict[tuple[int, date], list[Decimal]] = defaultdict(
        lambda: [Decimal(0), Decimal(0)]
    )
    for row in data["ai_requests"]:
        if row["project_id"] is None or row["cost_usd"] is None:
            continue
        month = row["requested_at"].astimezone(KST).date().replace(day=1)
        index = 0 if row["cost_status"] == CostStatus.CONFIRMED else 1
        totals[(row["project_id"], month)][index] += row["cost_usd"]
    # 화면(project_budgets.build_row)처럼 구독료는 확정 쪽에 더한다
    for row in data["subscription_costs"]:
        if row["project_id"] is not None:
            totals[(row["project_id"], row["applied_month"])][0] += row["amount"]
    return {key: (value[0], value[1]) for key, value in totals.items()}


@pytest.mark.parametrize(
    ("project_code", "month", "expected"),
    [
        ("PRJ-PDP-DEV", SEPTEMBER, BudgetStatus.WARNING),
        ("PRJ-PDP-DEV", OCTOBER, BudgetStatus.NORMAL),
        ("PRJ-PDP-DEV", NOVEMBER, BudgetStatus.NORMAL),
        ("PRJ-CUST-RENEWAL", OCTOBER, BudgetStatus.UNSET),
        ("PRJ-PATRON-POC", OCTOBER, BudgetStatus.NORMAL),
    ],
)
def test_project_budgets_include_subscriptions(
    project_usage: dict, project_code: str, month: date, expected: BudgetStatus
) -> None:
    owner = project_id(project_code)
    amount = budgets.monthly_amount(BudgetScopeType.PROJECT, owner, month)
    confirmed, estimated = project_usage.get((owner, month), (Decimal(0), Decimal(0)))

    assert evaluate_budget(amount, confirmed, estimated).status == expected

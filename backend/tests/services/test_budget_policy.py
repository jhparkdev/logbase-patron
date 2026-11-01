"""예산 사용률·상태 판단 테스트. DB 없이 경계값을 검증한다."""

from decimal import Decimal

import pytest

from app.services.budget_policy import BudgetStatus, evaluate_budget, share_of_budget


@pytest.mark.parametrize(
    ("confirmed", "expected"),
    [
        ("79.99", BudgetStatus.NORMAL),
        ("80", BudgetStatus.WARNING),
        ("99.99", BudgetStatus.WARNING),
        ("100", BudgetStatus.OVER),
        ("100.01", BudgetStatus.OVER),
    ],
)
def test_status_changes_exactly_at_80_and_100_percent(
    confirmed: str, expected: BudgetStatus
) -> None:
    result = evaluate_budget(Decimal(100), Decimal(confirmed), Decimal(0))

    assert result.status == expected


def test_status_is_judged_before_rounding() -> None:
    # 반올림하면 80.00%지만 실제로는 80% 미만이다
    result = evaluate_budget(Decimal(100), Decimal("79.999"), Decimal(0))

    assert result.status == BudgetStatus.NORMAL
    assert result.usage_pct == Decimal("80.00")


def test_estimated_cost_counts_toward_status() -> None:
    result = evaluate_budget(Decimal(100), Decimal(70), Decimal(10))

    assert result.status == BudgetStatus.WARNING
    assert result.used_usd == Decimal(80)
    assert result.usage_pct == Decimal("80.00")
    assert result.confirmed_usage_pct == Decimal("70.00")
    assert result.remaining_usd == Decimal(20)


def test_remaining_is_negative_when_over_budget() -> None:
    result = evaluate_budget(Decimal(10), Decimal(12), Decimal(0))

    assert result.remaining_usd == Decimal(-2)


def test_no_budget_is_unset_and_not_zero_percent() -> None:
    result = evaluate_budget(None, Decimal(5), Decimal(1))

    assert result.status == BudgetStatus.UNSET
    assert result.used_usd == Decimal(6)
    assert result.usage_pct is None
    assert result.confirmed_usage_pct is None
    assert result.remaining_usd is None


def test_share_of_budget_is_none_without_a_budget() -> None:
    assert share_of_budget(Decimal(5), None) is None


def test_share_of_budget_uses_the_given_amount() -> None:
    assert share_of_budget(Decimal(5), Decimal(20)) == Decimal("25.00")

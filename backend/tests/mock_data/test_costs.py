"""app/mock_data/costs.py 테스트: 비용 상태 판단(현재 시각을 인자로 받는 순수 함수)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.mock_data import costs, outcomes
from app.mock_data.period import kst
from app.models import CostSource, CostStatus, ErrorType

COMPLETED = kst(10, 1, 12)
NOW = kst(11, 6, 9)
COST = Decimal("0.0123")
PRICE_ID = 1


def test_api_response_cost_is_confirmed_when_the_call_completes() -> None:
    fields = costs.cost_fields(
        outcomes.SUCCESS, costs.CostPath.API_RESPONSE, COST, COMPLETED, PRICE_ID, NOW
    )

    assert fields["cost_status"] == CostStatus.CONFIRMED
    assert fields["cost_source"] == CostSource.API_RESPONSE
    assert fields["cost_usd"] == COST
    assert fields["cost_confirmed_at"] == COMPLETED
    assert fields["reconciled_at"] is None


@pytest.mark.parametrize(
    ("age", "reconciled"),
    [
        (costs.RECONCILE_DELAY - timedelta(seconds=1), False),
        (costs.RECONCILE_DELAY, True),
        (costs.RECONCILE_DELAY + timedelta(seconds=1), True),
    ],
)
def test_missing_cost_is_reconciled_only_after_the_delay(
    age: timedelta, reconciled: bool
) -> None:
    fields = costs.cost_fields(
        outcomes.SUCCESS, costs.CostPath.MISSING, COST, NOW - age, PRICE_ID, NOW
    )

    if reconciled:
        assert fields["cost_status"] == CostStatus.CONFIRMED
        assert fields["cost_source"] == CostSource.GENERATION_LOOKUP
        assert fields["cost_usd"] == COST
        assert fields["reconciled_at"] == NOW - age + costs.RECONCILE_DELAY
    else:
        assert fields["cost_status"] == CostStatus.UNKNOWN
        assert fields["cost_usd"] is None
        assert fields["cost_source"] is None
        assert fields["reconciled_at"] is None


def test_estimated_cost_keeps_the_price_it_was_based_on() -> None:
    fields = costs.cost_fields(
        outcomes.SUCCESS, costs.CostPath.ESTIMATED, COST, COMPLETED, PRICE_ID, NOW
    )

    assert fields["cost_status"] == CostStatus.ESTIMATED
    assert fields["cost_source"] == CostSource.PRICE_ESTIMATE
    assert fields["price_id"] == PRICE_ID
    assert fields["cost_confirmed_at"] is None


def test_routing_failure_is_confirmed_as_no_charge() -> None:
    outcome = outcomes.FAILURES[ErrorType.UNSUPPORTED_INPUT]
    fields = costs.cost_fields(
        outcome, costs.CostPath.API_RESPONSE, COST, COMPLETED, PRICE_ID, NOW
    )

    assert fields["cost_status"] == CostStatus.CONFIRMED
    assert fields["cost_source"] == CostSource.NO_CHARGE
    assert fields["cost_usd"] == Decimal(0)


@pytest.mark.parametrize(
    "error_type",
    [e for e in outcomes.FAILURES if e != ErrorType.UNSUPPORTED_INPUT],
)
def test_other_failures_leave_the_cost_unknown_not_zero(error_type: ErrorType) -> None:
    fields = costs.cost_fields(
        outcomes.FAILURES[error_type],
        costs.CostPath.API_RESPONSE,
        COST,
        COMPLETED,
        PRICE_ID,
        NOW,
    )

    assert fields["cost_status"] == CostStatus.UNKNOWN
    assert fields["cost_usd"] is None

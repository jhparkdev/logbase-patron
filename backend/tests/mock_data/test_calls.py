"""app/mock_data/calls.py 테스트: 호출 1건의 Token·지연·결과·비용."""

from datetime import timedelta
from decimal import Decimal
from random import Random

import pytest

from app.mock_data import calls, outcomes
from app.mock_data.model_book import ModelBook, build_model_book
from app.mock_data.period import kst
from app.mock_data.snapshot import load_snapshot
from app.models import (
    CallPurpose,
    CostStatus,
    ErrorType,
    RequestStatus,
    UsageOrigin,
)

SONNET_5 = 1
COMPLETED = kst(10, 1, 12)
NOW = kst(11, 6, 9)
COST = Decimal("0.0123")
PRICE_ID = 1


@pytest.fixture(scope="module")
def book() -> ModelBook:
    return build_model_book(load_snapshot())


def _spec() -> calls.CallSpec:
    return calls.CallSpec(
        usage_origin=UsageOrigin.CUSTOMER_SERVICE,
        key_id=2,
        service_id=1,
        model_id=SONNET_5,
        shape=calls.Shape.DESCRIPTION,
        call_purpose=CallPurpose.GENERATION,
        customer_id=1,
    )


def test_cached_input_tokens_are_charged_at_the_cache_read_price(
    book: ModelBook,
) -> None:
    entry = book[SONNET_5]
    cost = calls.call_cost(entry, input_tokens=1000, output_tokens=100, cached=400)

    expected = (
        600 * entry.input_price
        + 400 * entry.cache_read_price
        + 100 * entry.output_price
    )
    assert cost == expected.quantize(calls.COST_QUANTUM)


def test_successful_call_row_has_consistent_tokens_and_timing(
    book: ModelBook,
) -> None:
    rng = Random(5)

    for _ in range(100):
        row = calls.build_call(_spec(), COMPLETED, outcomes.SUCCESS, book, rng, NOW)
        assert row["status"] == RequestStatus.SUCCESS
        assert row["error_type"] is None
        assert row["cached_tokens"] <= row["input_tokens"]
        assert row["reasoning_tokens"] <= row["output_tokens"]
        latency = row["completed_at"] - row["requested_at"]
        assert latency == timedelta(milliseconds=row["latency_ms"])
        assert row["external_generation_id"] is not None


def test_failed_call_row_has_no_tokens_and_no_generation(
    book: ModelBook,
) -> None:
    outcome = outcomes.FAILURES[ErrorType.RATE_LIMIT]
    row = calls.build_call(_spec(), COMPLETED, outcome, book, Random(5), NOW)

    assert row["status"] == RequestStatus.FAILED
    assert row["input_tokens"] is None and row["output_tokens"] is None
    assert row["external_generation_id"] is None
    assert row["cost_status"] == CostStatus.UNKNOWN

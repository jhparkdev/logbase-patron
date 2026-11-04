"""app/mock_data/reconciliation.py 테스트: 비용 정정 이력, Key 사용량 스냅샷, 사용량 대조."""

from decimal import Decimal

import pytest

from app.mock_data import reconciliation
from app.mock_data.connection_tests import generate_connection_tests
from app.mock_data.internal import generate_development_calls
from app.mock_data.keys import poc_key
from app.mock_data.model_book import build_model_book
from app.mock_data.period import PERIOD_END
from app.mock_data.simulations import generate_simulations
from app.mock_data.snapshot import load_snapshot
from app.mock_data.usage import generate_customer_usage
from app.models import Comparability, CostSource, CostStatus


@pytest.fixture(scope="module")
def requests() -> list:
    book = build_model_book(load_snapshot())
    return (
        generate_customer_usage(book).requests
        + generate_development_calls(book)
        + generate_connection_tests(book)
        + generate_simulations(book).requests
    )


def test_every_reconciled_call_has_exactly_one_adjustment(requests: list) -> None:
    adjustments = reconciliation.cost_adjustment_rows(requests)
    reconciled = {
        r["request_id"]: r for r in requests if r["reconciled_at"] is not None
    }

    assert reconciled
    assert sorted(a["request_id"] for a in adjustments) == sorted(reconciled)
    for adjustment in adjustments:
        call = reconciled[adjustment["request_id"]]
        assert adjustment["old_cost_status"] == CostStatus.UNKNOWN
        assert adjustment["old_cost_usd"] is None
        assert (
            adjustment["new_cost_status"] == call["cost_status"] == CostStatus.CONFIRMED
        )
        assert adjustment["new_cost_source"] == CostSource.GENERATION_LOOKUP
        assert adjustment["new_cost_usd"] == call["cost_usd"]
        assert adjustment["adjusted_at"] == call["reconciled_at"]
        assert adjustment["reason"]


def test_snapshots_track_the_cumulative_spend_of_the_poc_key(requests: list) -> None:
    snapshots = reconciliation.key_usage_snapshot_rows(requests)
    totals = [s["usage_total_usd"] for s in snapshots]

    assert snapshots
    assert all(s["key_id"] == poc_key().key_id for s in snapshots)
    assert totals == sorted(totals)
    assert all(s["captured_at"] <= PERIOD_END for s in snapshots)
    for snapshot in snapshots:
        assert (
            snapshot["limit_remaining_usd"]
            == snapshot["limit_usd"] - snapshot["usage_total_usd"]
        )


def test_comparable_reconciliation_difference_is_external_minus_patron(
    requests: list,
) -> None:
    snapshots = reconciliation.key_usage_snapshot_rows(requests)
    rows = reconciliation.usage_reconciliation_rows(requests, snapshots)
    comparable = [r for r in rows if r["comparability"] == Comparability.COMPARABLE]

    assert comparable
    for row in comparable:
        patron = row["patron_confirmed_usd"] + row["patron_estimated_usd"]
        assert row["difference_usd"] == row["external_usage_usd"] - patron
        assert row["difference_usd"] >= Decimal(0)
        assert row["period_end"] > row["period_start"]


def test_mock_keys_without_snapshots_are_uncomparable(requests: list) -> None:
    snapshots = reconciliation.key_usage_snapshot_rows(requests)
    rows = reconciliation.usage_reconciliation_rows(requests, snapshots)
    uncomparable = [r for r in rows if r["comparability"] == Comparability.UNCOMPARABLE]

    assert uncomparable
    for row in uncomparable:
        assert row["external_usage_usd"] is None and row["difference_usd"] is None
        assert row["start_snapshot_id"] is None and row["end_snapshot_id"] is None


def test_patron_totals_match_the_calls_in_the_period(requests: list) -> None:
    snapshots = reconciliation.key_usage_snapshot_rows(requests)
    for row in reconciliation.usage_reconciliation_rows(requests, snapshots):
        calls = [
            r
            for r in requests
            if r["key_id"] == row["key_id"]
            and row["period_start"] <= r["requested_at"] < row["period_end"]
        ]
        confirmed = sum(
            (r["cost_usd"] for r in calls if r["cost_status"] == CostStatus.CONFIRMED),
            Decimal(0),
        )
        unknown = sum(1 for r in calls if r["cost_status"] == CostStatus.UNKNOWN)
        assert row["patron_confirmed_usd"] == confirmed
        assert row["patron_unknown_count"] == unknown

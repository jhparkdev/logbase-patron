"""app/mock_data/usage.py 테스트: 고객 서비스 작업과 호출 약 4천여 건."""

from collections import Counter
from datetime import timedelta

import pytest

from app.mock_data import usage
from app.mock_data.keys import KEYS
from app.mock_data.model_book import ModelBook, build_model_book
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import CUSTOMERS, service_id
from app.mock_data.period import KST, PERIOD_END, PERIOD_START, kst
from app.mock_data.snapshot import load_snapshot
from app.models import CostSource, CostStatus, RequestStatus, UsageOrigin

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}
KEYS_BY_ID = {key.key_id: key for key in KEYS}
CUSTOMERS_BY_ID = {c.customer_id: c for c in CUSTOMERS}
# 결정 사항: 전체 호출 약 5천 건 중 고객 호출이 대부분을 차지한다.
CUSTOMER_CALLS_MIN = 3800
CUSTOMER_CALLS_MAX = 4600


@pytest.fixture(scope="module")
def book() -> ModelBook:
    return build_model_book(load_snapshot())


@pytest.fixture(scope="module")
def generated(book: ModelBook) -> usage.CustomerUsage:
    return usage.generate_customer_usage(book)


def test_same_input_generates_the_same_rows(
    book: ModelBook, generated: usage.CustomerUsage
) -> None:
    assert usage.generate_customer_usage(book) == generated


def test_volume_matches_the_decided_scale(generated: usage.CustomerUsage) -> None:
    assert CUSTOMER_CALLS_MIN <= len(generated.requests) <= CUSTOMER_CALLS_MAX


def test_ids_are_unique(generated: usage.CustomerUsage) -> None:
    request_ids = [row["request_id"] for row in generated.requests]
    generation_ids = [
        row["external_generation_id"]
        for row in generated.requests
        if row["external_generation_id"] is not None
    ]

    assert len(set(request_ids)) == len(request_ids)
    assert len(set(generation_ids)) == len(generation_ids)
    assert len({row["task_id"] for row in generated.tasks}) == len(generated.tasks)


def test_customer_calls_are_never_mixed_with_internal_owners(
    generated: usage.CustomerUsage,
) -> None:
    for row in generated.requests:
        assert row["usage_origin"] == UsageOrigin.CUSTOMER_SERVICE
        assert row["project_id"] is None
        assert row["executed_by"] is None


def test_calls_use_a_key_of_their_own_customer_and_service(
    generated: usage.CustomerUsage,
) -> None:
    for row in generated.requests:
        key = KEYS_BY_ID[row["key_id"]]
        assert (
            key.service_code is None
            or service_id(key.service_code) == row["service_id"]
        )
        if row["customer_id"] is not None:
            assert key.customer_id == row["customer_id"]


def test_some_calls_stay_unclassified(generated: usage.CustomerUsage) -> None:
    unclassified = [row for row in generated.requests if row["customer_id"] is None]

    assert 0 < len(unclassified) < len(generated.requests) / 100


def test_calls_fall_inside_each_customer_contract_and_the_period(
    generated: usage.CustomerUsage,
) -> None:
    for row in generated.requests:
        assert PERIOD_START <= row["requested_at"]
        assert row["completed_at"] <= PERIOD_END
        customer = CUSTOMERS_BY_ID.get(row["customer_id"])
        if customer is not None:
            assert customer.usage_from <= row["requested_at"]
            assert (
                customer.usage_until is None
                or row["requested_at"] < customer.usage_until
            )


def test_every_call_uses_a_model_active_at_that_time(
    generated: usage.CustomerUsage,
) -> None:
    for row in generated.requests:
        plan = PLANS[row["model_id"]]
        assert (
            plan.activated_at is not None and plan.activated_at <= row["requested_at"]
        )
        assert plan.deactivated_at is None or row["requested_at"] < plan.deactivated_at


def test_retries_follow_a_failed_attempt(generated: usage.CustomerUsage) -> None:
    by_id = {row["request_id"]: row for row in generated.requests}
    retries = [row for row in generated.requests if row["attempt_no"] > 1]

    assert retries
    for row in retries:
        parent = by_id[row["parent_request_id"]]
        assert parent["status"] != RequestStatus.SUCCESS
        assert parent["completed_at"] <= row["requested_at"]
        assert parent["task_id"] == row["task_id"]


def test_tasks_span_all_of_their_calls(generated: usage.CustomerUsage) -> None:
    calls_by_task: dict[object, list] = {}
    for row in generated.requests:
        if row["task_id"] is not None:
            calls_by_task.setdefault(row["task_id"], []).append(row)

    for task in generated.tasks:
        task_calls = calls_by_task[task["task_id"]]
        assert task["started_at"] <= min(c["requested_at"] for c in task_calls)
        assert task["completed_at"] == max(c["completed_at"] for c in task_calls)
        assert {c["customer_id"] for c in task_calls} == {task["customer_id"]}


def test_unknown_cost_is_null_and_no_charge_only_for_failures(
    generated: usage.CustomerUsage,
) -> None:
    statuses = Counter(row["cost_status"] for row in generated.requests)

    assert statuses[CostStatus.UNKNOWN] > 0
    assert statuses[CostStatus.ESTIMATED] > 0
    for row in generated.requests:
        assert (row["cost_status"] == CostStatus.UNKNOWN) == (row["cost_usd"] is None)
        if row["cost_source"] == CostSource.NO_CHARGE:
            assert row["status"] == RequestStatus.FAILED


def test_some_missing_costs_were_reconciled(generated: usage.CustomerUsage) -> None:
    reconciled = [row for row in generated.requests if row["reconciled_at"] is not None]

    assert reconciled
    assert all(row["reconciled_at"] <= PERIOD_END for row in reconciled)


def test_november_is_busier_per_day_than_october(
    generated: usage.CustomerUsage,
) -> None:
    def daily_average(month: int, days: int) -> float:
        count = sum(
            1
            for row in generated.requests
            if row["requested_at"].astimezone(KST).month == month
        )
        return count / days

    november_days = (PERIOD_END - kst(11, 1)) / timedelta(days=1)
    assert daily_average(11, november_days) > daily_average(10, 31)

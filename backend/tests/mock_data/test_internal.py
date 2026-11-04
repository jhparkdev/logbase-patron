"""app/mock_data/internal.py 테스트: 내부 개발 호출."""

import pytest

from app.mock_data import internal
from app.mock_data.keys import KEYS
from app.mock_data.model_book import ModelBook, build_model_book
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import service_id
from app.mock_data.period import PERIOD_END, PERIOD_START
from app.mock_data.snapshot import load_snapshot
from app.models import CallPurpose, UsageOrigin

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}
KEYS_BY_ID = {key.key_id: key for key in KEYS}


@pytest.fixture(scope="module")
def book() -> ModelBook:
    return build_model_book(load_snapshot())


@pytest.fixture(scope="module")
def development(book: ModelBook) -> list:
    return internal.generate_development_calls(book)


def test_development_calls_belong_to_the_project_of_their_key(
    development: list,
) -> None:
    assert development
    for row in development:
        key = KEYS_BY_ID[row["key_id"]]
        assert row["usage_origin"] == UsageOrigin.INTERNAL_DEVELOPMENT
        assert row["customer_id"] is None
        assert row["executed_by"] is None
        assert row["project_id"] == key.project_id
        assert row["service_id"] == service_id(key.service_code)


def test_development_calls_use_active_models_inside_the_period(
    development: list,
) -> None:
    for row in development:
        plan = PLANS[row["model_id"]]
        assert PERIOD_START <= row["requested_at"] and row["completed_at"] <= PERIOD_END
        assert (
            plan.activated_at is not None and plan.activated_at <= row["requested_at"]
        )
        assert plan.deactivated_at is None or row["requested_at"] < plan.deactivated_at


def test_new_models_are_tried_internally_soon_after_activation(
    development: list,
) -> None:
    experimented = {
        row["model_id"]
        for row in development
        if row["call_purpose"] == CallPurpose.EXPERIMENT
    }
    activated_in_period = {
        plan.model_id
        for plan in MODEL_PLANS
        if plan.activated_at is not None and plan.activated_at >= PERIOD_START
    }

    assert activated_in_period <= experimented

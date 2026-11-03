"""app/mock_data/model_plans.py 테스트: 모델 등록·활성화·비활성화 일정."""

from datetime import UTC, datetime

import pytest

from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.period import PERIOD_END
from app.mock_data.snapshot import Snapshot, load_snapshot


@pytest.fixture(scope="module")
def snapshot() -> Snapshot:
    return load_snapshot()


def test_every_plan_matches_one_snapshot_model(snapshot: Snapshot) -> None:
    planned = [plan.openrouter_model_id for plan in MODEL_PLANS]
    model_ids = [plan.model_id for plan in MODEL_PLANS]

    assert len(set(planned)) == len(planned)
    assert len(set(model_ids)) == len(model_ids)
    assert set(planned) == {model.id for model in snapshot.models}


def test_no_model_is_registered_before_its_release(snapshot: Snapshot) -> None:
    released = {
        model.id: datetime.fromtimestamp(model.created, UTC)
        for model in snapshot.models
    }

    for plan in MODEL_PLANS:
        assert released[plan.openrouter_model_id] < plan.registered_at


def test_lifecycle_times_are_ordered_and_never_after_the_mock_period() -> None:
    for plan in MODEL_PLANS:
        times = [plan.registered_at, plan.activated_at, plan.deactivated_at]
        present = [t for t in times if t is not None]
        assert present == sorted(present)
        assert present[-1] <= PERIOD_END


def test_connection_test_happens_after_registration_and_before_activation() -> None:
    for plan in MODEL_PLANS:
        assert plan.registered_at < plan.tested_at <= PERIOD_END
        if plan.activated_at is not None:
            assert plan.tested_at < plan.activated_at


def test_replaced_models_go_inactive_only_after_the_successor_is_active() -> None:
    plans = {plan.openrouter_model_id: plan for plan in MODEL_PLANS}
    replaced = [plan for plan in plans.values() if plan.replaced_by is not None]

    assert replaced
    for plan in replaced:
        successor = plans[plan.replaced_by]
        assert successor.activated_at is not None
        assert plan.deactivated_at is not None
        assert successor.activated_at < plan.deactivated_at

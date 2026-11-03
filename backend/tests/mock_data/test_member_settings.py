"""app/mock_data/member_settings.py 테스트: 모델 즐겨찾기."""

from app.mock_data import member_settings
from app.mock_data.members import USERS
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.model_profiles import PROFILES
from app.mock_data.period import PERIOD_END

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}


def test_favorites_point_at_active_models_and_their_providers() -> None:
    rows = member_settings.favorite_rows()
    keys = [(r["user_id"], r["model_id"], r["execution_provider"]) for r in rows]

    assert rows
    assert len(set(keys)) == len(keys)
    for row in rows:
        plan = PLANS[row["model_id"]]
        assert plan.deactivated_at is None
        assert row["execution_provider"] in PROFILES[plan.openrouter_model_id].providers
        assert plan.registered_at <= row["created_at"] <= PERIOD_END


def test_favorites_belong_to_members_who_could_act_then() -> None:
    members = {u.user_id: u for u in USERS}

    for row in member_settings.favorite_rows():
        assert members[row["user_id"]].can_act_at(row["created_at"])

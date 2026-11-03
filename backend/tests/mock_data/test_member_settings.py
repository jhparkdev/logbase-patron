"""app/mock_data/member_settings.py 테스트: 모델 즐겨찾기와 구성원별 Command Code Key."""

import re

from app.mock_data import member_settings
from app.mock_data.members import USERS
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.model_profiles import PROFILES
from app.mock_data.period import PERIOD_END

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}
SECRET_REF = re.compile(r"^COMMAND_CODE_KEY_[A-Z0-9_]+$")


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


def test_command_code_keys_store_only_reference_names() -> None:
    rows = member_settings.command_code_key_rows()
    refs = [row["secret_ref"] for row in rows]

    assert len(set(refs)) == len(refs)
    assert all(SECRET_REF.match(ref) for ref in refs)
    for row in rows:
        assert row["member_name"] == row["member_name"].strip() != ""


def test_each_member_has_at_most_one_active_command_code_key() -> None:
    active = [
        row["member_name"]
        for row in member_settings.command_code_key_rows()
        if row["is_active"]
    ]

    assert len(set(active)) == len(active)


def test_deactivated_member_key_is_inactive() -> None:
    member = next(u for u in USERS if not u.is_active)
    rows = [
        r
        for r in member_settings.command_code_key_rows()
        if r["member_name"] == member.name
    ]

    assert rows
    assert not any(row["is_active"] for row in rows)

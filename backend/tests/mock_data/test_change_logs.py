"""app/mock_data/change_logs.py 테스트: 모델·Key·고객·예산·시나리오 변경 이력."""

from app.mock_data import change_logs
from app.mock_data.members import USERS
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.period import PERIOD_END
from app.mock_data.scenarios import CHANGED_AT
from app.models import ChangeAction


def _rows() -> list:
    return change_logs.change_log_rows()


def test_each_model_status_change_is_logged_at_its_planned_time() -> None:
    logged = {
        (row["entity_id"], row["changes"]["status"]["new"]): row["changed_at"]
        for row in _rows()
        if row["entity_type"] == "models"
        and row["action"] == ChangeAction.STATUS_CHANGE
    }

    for plan in MODEL_PLANS:
        if plan.activated_at is not None:
            assert logged[(str(plan.model_id), "ACTIVE")] == plan.activated_at
        if plan.deactivated_at is not None:
            assert logged[(str(plan.model_id), "INACTIVE")] == plan.deactivated_at


def test_member_deactivation_and_scenario_change_are_logged() -> None:
    rows = _rows()
    member = next(u for u in USERS if not u.is_active)

    assert any(
        row["entity_type"] == "users"
        and row["entity_id"] == str(member.user_id)
        and row["action"] == ChangeAction.DEACTIVATE
        and row["changed_at"] == member.deactivated_at
        for row in rows
    )
    assert any(
        row["entity_type"] == "test_scenarios" and row["changed_at"] == CHANGED_AT
        for row in rows
    )


def test_logs_have_a_valid_action_and_never_come_from_the_future() -> None:
    for row in _rows():
        assert row["action"] in ChangeAction
        assert isinstance(row["entity_id"], str)
        assert row["changed_at"] <= PERIOD_END
        assert row["changes"]


def test_changes_record_old_and_new_values() -> None:
    for row in _rows():
        for change in row["changes"].values():
            assert change.keys() == {"old", "new"}

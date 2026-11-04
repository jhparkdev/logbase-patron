"""app/mock_data/members.py 테스트: Patron 구성원 계정."""

from datetime import timedelta

from app.mock_data import members
from app.mock_data.period import PERIOD_END

# 기존 seed 계정. 팀원이 쓰던 로그인 정보를 그대로 쓸 수 있어야 한다.
EXISTING_ADMIN_EMAILS = {"admin1@patron.dev", "admin2@patron.dev"}


def test_existing_admin_accounts_are_kept_with_the_same_password_hash() -> None:
    rows = {row["email"]: row for row in members.user_rows()}

    assert EXISTING_ADMIN_EMAILS <= rows.keys()
    assert {rows[email]["password_hash"] for email in EXISTING_ADMIN_EMAILS} == {
        members.DEV_PASSWORD_HASH
    }


def test_members_share_the_dev_password_and_one_is_deactivated() -> None:
    rows = members.user_rows()

    assert len({row["user_id"] for row in rows}) == len(rows)
    assert len({row["email"] for row in rows}) == len(rows)
    assert {row["password_hash"] for row in rows} == {members.DEV_PASSWORD_HASH}
    assert len([row for row in rows if not row["is_active"]]) == 1


def test_every_member_row_is_marked_as_mock() -> None:
    assert all(row["is_mock"] is True for row in members.user_rows())


def test_last_login_never_falls_after_the_mock_period() -> None:
    for row in members.user_rows():
        last_login = row["last_login_at"]
        assert last_login is None or last_login <= PERIOD_END


def test_deactivated_member_cannot_act_after_deactivation() -> None:
    member = next(m for m in members.USERS if not m.is_active)

    assert member.deactivated_at is not None
    assert member.last_login_at is not None
    assert member.last_login_at < member.deactivated_at
    assert member.can_act_at(member.deactivated_at - timedelta(seconds=1))
    assert not member.can_act_at(member.deactivated_at)

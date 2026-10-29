"""관리 CLI의 계정·세션 변경을 patron_test의 롤백 세션에서 검증한다."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.models import AIRequest, User, UserSession
from app.schemas.auth import EMAIL_MAX_LENGTH, PASSWORD_MAX_LENGTH
from app.services import users
from tests.db_helpers import T0, Factory

PASSWORD = "cli-test-password"
USER_FIELDS = {"email": "admin@example.test", "name": "관리자", "user_code": "ADMIN"}


async def test_created_user_can_log_in(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    user = await users.create_user(
        db_session,
        email="  Admin@Example.Test  ",
        name=" 관리자 ",
        user_code=" ADMIN ",
        password=PASSWORD,
    )

    await db_session.refresh(user)
    assert user.email == USER_FIELDS["email"]
    assert user.name == USER_FIELDS["name"]
    assert user.user_code == USER_FIELDS["user_code"]
    assert user.is_active is True
    assert user.is_mock is False
    assert user.password_hash.startswith("$argon2id$")
    assert security.verify_password(PASSWORD, user.password_hash)
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == user.user_id


@pytest.mark.parametrize("length", [1, PASSWORD_MAX_LENGTH])
async def test_create_accepts_password_length_boundaries(
    db_session: AsyncSession, length: int
) -> None:
    password = "x" * length
    user = await users.create_user(db_session, **USER_FIELDS, password=password)
    assert security.verify_password(password, user.password_hash)


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "   "},
        {"email": "a" * (EMAIL_MAX_LENGTH + 1)},
        {"name": "   "},
        {"user_code": "   "},
        {"password": ""},
        {"password": "x" * (PASSWORD_MAX_LENGTH + 1)},
    ],
)
async def test_invalid_user_is_not_saved(
    db_session: AsyncSession, changes: dict[str, str]
) -> None:
    values = {**USER_FIELDS, "password": PASSWORD, **changes}
    with pytest.raises(users.UserCommandError) as error:
        await users.create_user(db_session, **values)
    assert PASSWORD not in str(error.value)
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize(
    "changes", [{"email": "  ADMIN@EXAMPLE.TEST "}, {"user_code": "ADMIN"}]
)
async def test_duplicate_user_does_not_replace_existing_account(
    db_session: AsyncSession, changes: dict[str, str]
) -> None:
    existing = await users.create_user(db_session, **USER_FIELDS, password=PASSWORD)
    original_id, original_hash = existing.user_id, existing.password_hash
    values = {
        "email": "other@example.test",
        "name": "다른 관리자",
        "user_code": "OTHER",
        "password": "different-password",
        **changes,
    }
    with pytest.raises(users.UserCommandError) as error:
        await users.create_user(db_session, **values)
    assert "different-password" not in str(error.value)
    stored = await db_session.get(User, original_id)
    assert stored is not None
    assert stored.password_hash == original_hash
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1


async def test_deactivate_revokes_all_sessions_and_preserves_history(
    db_session: AsyncSession, client: AsyncClient, factory: Factory
) -> None:
    user = await users.create_user(db_session, **USER_FIELDS, password=PASSWORD)
    for _ in range(2):
        response = await client.post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
        assert response.status_code == 200
    # 삭제 대상과 함께 보존 대상을 준비해, 다른 사용자의 세션과 기존 호출 이력이 남는지도 확인한다.
    other = await factory.user()
    other_session = await factory.user_session(user_id=other["user_id"])
    request = await factory.ai_request(
        usage_origin="SYSTEM_TEST", executed_by=user.user_id
    )

    assert (
        await users.deactivate_user(db_session, "  ADMIN@EXAMPLE.TEST ") == user.user_id
    )

    await db_session.refresh(user)
    assert user.is_active is False
    assert await db_session.get(AIRequest, request["request_id"]) is not None
    remaining = (await db_session.scalars(select(UserSession.session_id))).all()
    assert remaining == [other_session["session_id"]]
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (
        await client.post(
            "/api/auth/login", json={"email": user.email, "password": PASSWORD}
        )
    ).status_code == 401
    assert await users.deactivate_user(db_session, user.email) == user.user_id


async def test_deactivate_unknown_user_is_an_error(db_session: AsyncSession) -> None:
    with pytest.raises(users.UserCommandError):
        await users.deactivate_user(db_session, "missing@example.test")


async def test_cleanup_deletes_only_expired_sessions_at_boundary(
    db_session: AsyncSession, factory: Factory
) -> None:
    sessions = []
    # 현재 시각보다 1μs 전·같음·1μs 후에 만료되도록 해 삭제 경계(<= now)를 확인한다.
    for offset in [-1, 0, 1]:
        sessions.append(
            await factory.user_session(
                created_at=T0 - security.SESSION_TTL,
                expires_at=T0 + timedelta(microseconds=offset),
            )
        )

    assert await users.cleanup_sessions(db_session, now=T0) == 2
    remaining = (await db_session.scalars(select(UserSession.session_id))).all()
    assert remaining == [sessions[2]["session_id"]]
    assert await db_session.scalar(select(func.count()).select_from(User)) == 3
    assert await users.cleanup_sessions(db_session, now=T0) == 0

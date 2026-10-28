"""app/services/auth.py 테스트. 로그인·세션 확인·로그아웃이 DB에 남기는 결과를 확인한다."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.models import User, UserSession
from app.services import auth
from tests.db_helpers import T0, Factory

PASSWORD = "correct-password"
# Argon2 해시는 느리므로 모듈에서 한 번만 만든다.
PASSWORD_HASH = security.hash_password(PASSWORD)
ONE_MICROSECOND = timedelta(microseconds=1)


async def count_sessions(db_session: AsyncSession) -> int:
    return await db_session.scalar(select(func.count()).select_from(UserSession)) or 0


async def make_user(factory: Factory, **values: object) -> User:
    row = await factory.user(password_hash=PASSWORD_HASH, **values)
    user = await factory.session.get(User, row["user_id"])
    assert user is not None
    return user


async def deactivate(db_session: AsyncSession, user: User) -> None:
    await db_session.execute(
        update(User).where(User.user_id == user.user_id).values(is_active=False)
    )
    await db_session.refresh(user)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("admin@x.test", "admin@x.test"), ("  Admin@X.Test  ", "admin@x.test")],
)
def test_normalize_email(raw: str, expected: str) -> None:
    assert auth.normalize_email(raw) == expected


# 로그인


async def test_login_issues_session_and_records_login_time(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory)

    result = await auth.login(db_session, user.email, PASSWORD, now=T0)

    assert result is not None
    assert result.user.user_id == user.user_id
    stored = await db_session.scalar(
        select(UserSession).where(UserSession.user_id == user.user_id)
    )
    assert stored is not None
    assert stored.token_hash == security.hash_session_token(result.token)
    assert stored.created_at == T0
    assert stored.expires_at == T0 + security.SESSION_TTL
    await db_session.refresh(user)
    assert user.last_login_at == T0


async def test_login_ignores_email_case_and_spaces(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory, email="admin@x.test")

    result = await auth.login(db_session, "  ADMIN@x.test ", PASSWORD, now=T0)

    assert result is not None
    assert result.user.user_id == user.user_id


async def test_wrong_password_is_rejected_without_side_effects(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory)

    assert await auth.login(db_session, user.email, "wrong-password", now=T0) is None
    assert await count_sessions(db_session) == 0
    await db_session.refresh(user)
    assert user.last_login_at is None


async def test_unknown_email_is_rejected(db_session: AsyncSession) -> None:
    assert await auth.login(db_session, "nobody@x.test", PASSWORD, now=T0) is None
    assert await count_sessions(db_session) == 0


async def test_inactive_user_cannot_log_in(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory, is_active=False)

    assert await auth.login(db_session, user.email, PASSWORD, now=T0) is None
    assert await count_sessions(db_session) == 0


# 세션 확인


async def test_session_token_resolves_to_user(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory)
    result = await auth.login(db_session, user.email, PASSWORD, now=T0)
    assert result is not None

    resolved = await auth.get_session_user(db_session, result.token, now=T0)

    assert resolved is not None
    assert resolved.user_id == user.user_id


async def test_unknown_token_is_rejected(db_session: AsyncSession) -> None:
    token = security.new_session_token()

    assert await auth.get_session_user(db_session, token, now=T0) is None


@pytest.mark.parametrize(
    ("elapsed", "valid"),
    [
        (security.SESSION_TTL - ONE_MICROSECOND, True),
        (security.SESSION_TTL, False),
        (security.SESSION_TTL + ONE_MICROSECOND, False),
    ],
)
async def test_session_expires_after_ttl(
    db_session: AsyncSession, factory: Factory, elapsed: timedelta, valid: bool
) -> None:
    user = await make_user(factory)
    result = await auth.login(db_session, user.email, PASSWORD, now=T0)
    assert result is not None

    resolved = await auth.get_session_user(db_session, result.token, now=T0 + elapsed)

    assert (resolved is not None) is valid


async def test_session_of_deactivated_user_is_rejected(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory)
    result = await auth.login(db_session, user.email, PASSWORD, now=T0)
    assert result is not None

    await deactivate(db_session, user)

    assert await auth.get_session_user(db_session, result.token, now=T0) is None


# 로그아웃


async def test_logout_deletes_only_that_session(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await make_user(factory)
    first = await auth.login(db_session, user.email, PASSWORD, now=T0)
    second = await auth.login(db_session, user.email, PASSWORD, now=T0)
    assert first is not None and second is not None

    await auth.logout(db_session, first.token)

    assert await auth.get_session_user(db_session, first.token, now=T0) is None
    assert await auth.get_session_user(db_session, second.token, now=T0) is not None

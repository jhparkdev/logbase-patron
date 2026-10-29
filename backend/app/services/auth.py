"""로그인, 세션 확인, 로그아웃.

세션은 DB(user_sessions)에 토큰 해시로만 남긴다. 현재 시각은 호출하는 쪽이 넘겨준다.
"""

from datetime import datetime
from typing import NamedTuple

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.models import User, UserSession


class LoginResult(NamedTuple):
    user: User
    # 쿠키로 보낼 토큰 원문. DB에는 해시만 저장되어 있다.
    token: str


def normalize_email(email: str) -> str:
    """로그인과 계정 생성에서 같은 주소를 같은 계정으로 찾도록 공백을 지우고 소문자로 바꾼다."""
    return email.strip().lower()


async def login(
    session: AsyncSession, email: str, password: str, *, now: datetime
) -> LoginResult | None:
    """비밀번호가 맞는 활성 계정이면 세션을 만들고, 아니면 None을 돌려준다.

    실패 이유(계정 없음·비밀번호 틀림·비활성)는 호출하는 쪽에 알리지 않는다.
    계정이 없어도 더미 해시로 검증해, 응답 시간으로도 계정 유무가 드러나지 않게 한다.
    """
    user = await session.scalar(
        select(User).where(User.email == normalize_email(email))
    )
    # Argon2 검증은 CPU를 오래 쓰므로 이벤트 루프를 막지 않게 스레드에서 실행한다.
    password_matches = await run_in_threadpool(
        security.verify_password_or_dummy,
        password,
        user.password_hash if user is not None else None,
    )
    if user is None or not password_matches or not user.is_active:
        return None

    token = security.new_session_token()
    # created_at을 직접 넣는다. DB 기본값(now())을 쓰면 주입한 시각과 어긋나 만료 CHECK에 걸릴 수 있다.
    session.add(
        UserSession(
            user_id=user.user_id,
            token_hash=security.hash_session_token(token),
            created_at=now,
            expires_at=security.session_expires_at(now),
        )
    )
    user.last_login_at = now
    # DB 저장이 성공해야 라우터가 쿠키를 발급한다. 실패하면 토큰을 클라이언트에 넘기지 않는다.
    await session.commit()
    return LoginResult(user=user, token=token)


async def get_session_user(
    session: AsyncSession, token: str, *, now: datetime
) -> User | None:
    """유효한 세션(만료 전, 활성 사용자)의 사용자를 돌려준다. 아니면 None."""
    # 사용자도 함께 조회해, 세션 발급 이후 계정이 비활성화된 경우까지 확인한다.
    row = (
        await session.execute(
            select(UserSession.expires_at, User)
            .join(User, User.user_id == UserSession.user_id)
            .where(UserSession.token_hash == security.hash_session_token(token))
        )
    ).one_or_none()
    if row is None:
        return None
    expires_at, user = row
    if not security.is_session_valid(
        expires_at=expires_at, user_is_active=user.is_active, now=now
    ):
        return None
    return user


async def logout(session: AsyncSession, token: str) -> None:
    """이 토큰의 세션만 지운다. 같은 사용자의 다른 세션은 남는다."""
    await session.execute(
        delete(UserSession).where(
            UserSession.token_hash == security.hash_session_token(token)
        )
    )
    await session.commit()

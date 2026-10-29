"""관리 CLI의 계정 생성·비활성화와 만료 세션 정리."""

from datetime import datetime

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.models import User, UserSession
from app.schemas.auth import EMAIL_MAX_LENGTH, PASSWORD_MAX_LENGTH
from app.services.auth import normalize_email


class UserCommandError(Exception):
    """관리 명령에서 입력값이나 내부 정보를 노출하지 않고 보여 줄 오류."""


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    user_code: str,
    password: str,
) -> User:
    # CLI에서 만든 계정도 로그인 입력 제한을 만족해야 나중에 로그인할 수 있다.
    email, name, user_code = normalize_email(email), name.strip(), user_code.strip()
    if not email or len(email) > EMAIL_MAX_LENGTH or not name or not user_code:
        raise UserCommandError("이메일·이름·사용자 코드를 올바르게 입력하세요.")
    if not 1 <= len(password) <= PASSWORD_MAX_LENGTH:
        raise UserCommandError(f"비밀번호는 1~{PASSWORD_MAX_LENGTH}자여야 합니다.")
    user = User(
        email=email,
        name=name,
        user_code=user_code,
        password_hash=await run_in_threadpool(security.hash_password, password),
        is_active=True,
        # DB 기본값은 mock용 true라 관리 명령으로 만든 실제 계정은 명시적으로 구분한다.
        is_mock=False,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # 동시에 같은 계정을 만들어도 DB 고유 제약으로 거절하고, 실패한 트랜잭션을 정리한다.
        await session.rollback()
        raise UserCommandError(
            "이미 사용 중인 이메일 또는 사용자 코드입니다."
        ) from None
    return user


async def deactivate_user(session: AsyncSession, email: str) -> int:
    """사용자는 남기고 비활성화와 그 사용자의 모든 세션 삭제를 함께 확정한다."""
    user = await session.scalar(
        select(User).where(User.email == normalize_email(email)).with_for_update()
    )
    if user is None:
        raise UserCommandError("해당 사용자를 찾을 수 없습니다.")
    user.is_active = False
    await session.execute(
        delete(UserSession).where(UserSession.user_id == user.user_id)
    )
    await session.commit()
    return user.user_id


async def cleanup_sessions(session: AsyncSession, *, now: datetime) -> int:
    """만료 시각과 같거나 지난 세션만 삭제한다. 사용자·호출 이력은 유지한다."""
    # 이 정리를 실행하지 않아도 만료 세션은 인증에서 거절된다. 이 명령은 남은 행을 치운다.
    result = await session.execute(
        delete(UserSession).where(UserSession.expires_at <= now)
    )
    await session.commit()
    return result.rowcount

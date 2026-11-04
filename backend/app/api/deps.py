"""여러 라우터가 함께 쓰는 의존성."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, status

from app.api.errors import ApiError
from app.api.session_cookie import SessionTokenCookie
from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import User
from app.schemas.common import ErrorCode
from app.services import auth

UNAUTHENTICATED_MESSAGE = "로그인이 필요합니다."
ORIGIN_NOT_ALLOWED_MESSAGE = "허용되지 않은 곳에서 보낸 요청입니다."
# 쿠키가 자동으로 실려 가는 요청 중 서버 상태를 바꾸는 것. 다른 사이트가 보내는 위조 요청을 막는다.
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_now() -> datetime:
    """현재 시각(UTC). 테스트는 app.dependency_overrides로 고정 시각을 넣는다."""
    return datetime.now(UTC)


NowDep = Annotated[datetime, Depends(get_now)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_allowed_origin(request: Request, settings: SettingsDep) -> None:
    """상태를 바꾸는 요청은 Origin 헤더가 ALLOWED_ORIGIN과 같을 때만 받는다.

    Origin이 없거나 ALLOWED_ORIGIN이 설정되지 않았으면 거절한다. CORS는 켜지 않는다.
    """
    if request.method not in STATE_CHANGING_METHODS:
        return
    origin = request.headers.get("origin")
    if settings.allowed_origin is None or origin != settings.allowed_origin:
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            ErrorCode.ORIGIN_NOT_ALLOWED,
            ORIGIN_NOT_ALLOWED_MESSAGE,
        )


def unauthenticated() -> ApiError:
    return ApiError(
        status.HTTP_401_UNAUTHORIZED,
        ErrorCode.UNAUTHENTICATED,
        UNAUTHENTICATED_MESSAGE,
    )


def require_session_token(token: SessionTokenCookie = None) -> str:
    """세션 쿠키의 토큰 원문. 쿠키가 없으면 401."""
    # 여기서는 토큰 유무만 확인한다. DB 세션의 유효성은 get_current_user에서 검사한다.
    if not token:
        raise unauthenticated()
    return token


SessionTokenDep = Annotated[str, Depends(require_session_token)]


async def get_current_user(
    session: SessionDep, now: NowDep, token: SessionTokenDep
) -> User:
    """유효한 세션의 사용자. 사용자 상태는 매 요청 DB에서 다시 확인한다."""
    user = await auth.get_session_user(session, token, now=now)
    if user is None:
        raise unauthenticated()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]

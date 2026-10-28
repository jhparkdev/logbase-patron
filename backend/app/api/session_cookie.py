"""세션 쿠키의 이름·속성. 발급과 삭제가 같은 값을 쓰도록 한 곳에 둔다."""

from typing import Annotated, Literal

from fastapi import Cookie, Response

from app.security import SESSION_TTL

SESSION_COOKIE_NAME = "patron_session"
# 프론트엔드는 /api만 호출하므로 쿠키도 /api 요청에만 실어 보낸다. 삭제할 때도 같은 path를 써야 지워진다.
SESSION_COOKIE_PATH = "/api"
SESSION_COOKIE_SAMESITE: Literal["lax"] = "lax"
# 토큰 수명과 쿠키 수명은 같은 상수에서 나온다.
SESSION_COOKIE_MAX_AGE = int(SESSION_TTL.total_seconds())

SessionTokenCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)]


def set_session_cookie(response: Response, token: str, *, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_COOKIE_MAX_AGE,
        path=SESSION_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
    )

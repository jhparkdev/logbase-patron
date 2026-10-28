"""로그인, 로그아웃, 현재 사용자. 세션 토큰은 응답 본문에 넣지 않고 쿠키로만 주고받는다."""

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUserDep, NowDep, SessionTokenDep, SettingsDep
from app.api.errors import ApiError
from app.api.session_cookie import clear_session_cookie, set_session_cookie
from app.db import SessionDep
from app.schemas.auth import CurrentUserRead, LoginRequest
from app.schemas.common import ErrorCode, ErrorResponse
from app.services import auth

# 실패 이유를 나누지 않는 한 가지 문구. 계정 존재 여부를 드러내지 않기 위해서다.
INVALID_CREDENTIALS_MESSAGE = "이메일 또는 비밀번호가 올바르지 않습니다."
UNAUTHORIZED_RESPONSE = {status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}}

# 로그인 없이 부르는 경로(로그인)와 로그인이 필요한 경로를 나눠 main.py에서 따로 등록한다.
public_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])


@public_router.post("/login", responses=UNAUTHORIZED_RESPONSE)
async def login(
    body: LoginRequest,
    response: Response,
    session: SessionDep,
    now: NowDep,
    settings: SettingsDep,
) -> CurrentUserRead:
    result = await auth.login(
        session, body.email, body.password.get_secret_value(), now=now
    )
    if result is None:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.INVALID_CREDENTIALS,
            INVALID_CREDENTIALS_MESSAGE,
        )
    set_session_cookie(response, result.token, secure=settings.session_cookie_secure)
    return CurrentUserRead.model_validate(result.user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNAUTHORIZED_RESPONSE,
)
async def logout(
    _: CurrentUserDep,
    token: SessionTokenDep,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    await auth.logout(session, token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, secure=settings.session_cookie_secure)
    return response


@router.get("/me", responses=UNAUTHORIZED_RESPONSE)
async def read_me(user: CurrentUserDep) -> CurrentUserRead:
    return CurrentUserRead.model_validate(user)

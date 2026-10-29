"""app/api/auth.py 테스트. 로그인·현재 사용자·로그아웃의 HTTP 계약과 보안 경계를 확인한다."""

from datetime import timedelta

from fastapi import FastAPI, status
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.api.session_cookie import SESSION_COOKIE_NAME, SESSION_COOKIE_PATH
from app.config import get_settings
from app.models import User, UserSession
from app.schemas.auth import PASSWORD_MAX_LENGTH
from tests.db_helpers import T0, Factory

PASSWORD = "correct-password"
PASSWORD_HASH = security.hash_password(PASSWORD)
LOGIN = "/api/auth/login"
LOGOUT = "/api/auth/logout"
ME = "/api/auth/me"
SESSION_TTL_SECONDS = int(security.SESSION_TTL.total_seconds())


async def make_user(factory: Factory, **values: object) -> dict[str, object]:
    row = await factory.user(password_hash=PASSWORD_HASH, **values)
    return dict(row)


async def log_in(client: AsyncClient, email: object) -> Response:
    return await client.post(LOGIN, json={"email": email, "password": PASSWORD})


def session_cookie_header(response: Response) -> str:
    headers = [
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{SESSION_COOKIE_NAME}=")
    ]
    assert len(headers) == 1
    return headers[0]


def cookie_attributes(header: str) -> dict[str, str]:
    """'name=value; HttpOnly; Path=/api' → {'httponly': '', 'path': '/api'} (이름=값 부분 제외)"""
    attributes: dict[str, str] = {}
    for part in header.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        attributes[key.lower()] = value
    return attributes


def cookie_value(header: str) -> str:
    return header.split(";")[0].partition("=")[2]


def with_token(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


# 로그인


async def test_login_sets_session_cookie_only(
    client: AsyncClient, factory: Factory
) -> None:
    user = await make_user(factory)

    response = await log_in(client, user["email"])

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "user_id": user["user_id"],
        "user_code": user["user_code"],
        "name": user["name"],
        "email": user["email"],
    }
    header = session_cookie_header(response)
    assert cookie_value(header) not in response.text
    attributes = cookie_attributes(header)
    assert "httponly" in attributes
    assert "secure" in attributes
    assert attributes["samesite"] == "lax"
    assert attributes["path"] == SESSION_COOKIE_PATH
    assert attributes["max-age"] == str(SESSION_TTL_SECONDS)


async def test_session_cookie_is_not_secure_when_turned_off(
    app: FastAPI, client: AsyncClient, factory: Factory
) -> None:
    test_settings = app.dependency_overrides[get_settings]()
    settings = test_settings.model_copy(update={"session_cookie_secure": False})
    app.dependency_overrides[get_settings] = lambda: settings
    user = await make_user(factory)

    response = await log_in(client, user["email"])

    assert "secure" not in cookie_attributes(session_cookie_header(response))


async def test_login_failures_look_the_same(
    client: AsyncClient, factory: Factory
) -> None:
    """계정 없음, 비밀번호 틀림, 비활성 계정을 응답으로 구분할 수 없어야 한다."""
    active = await make_user(factory)
    inactive = await make_user(factory, is_active=False)

    unknown = await log_in(client, "nobody@example.test")
    wrong = await client.post(
        LOGIN, json={"email": active["email"], "password": "wrong-password"}
    )
    disabled = await log_in(client, inactive["email"])

    assert unknown.status_code == status.HTTP_401_UNAUTHORIZED
    assert unknown.json()["code"] == "INVALID_CREDENTIALS"
    for response in (wrong, disabled):
        assert response.status_code == unknown.status_code
        assert response.json() == unknown.json()
        assert "set-cookie" not in response.headers


async def test_too_long_password_is_rejected_without_echo(
    client: AsyncClient,
) -> None:
    password = "p" * (PASSWORD_MAX_LENGTH + 1)

    response = await client.post(
        LOGIN, json={"email": "admin@example.test", "password": password}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert password not in response.text


async def test_longest_allowed_password_is_checked(client: AsyncClient) -> None:
    response = await client.post(
        LOGIN,
        json={"email": "admin@example.test", "password": "p" * PASSWORD_MAX_LENGTH},
    )

    # 길이 제한에 걸리는 422가 아니라, 자격 증명 검증까지 진행한 결과인 401이어야 한다.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# 현재 사용자


async def test_me_returns_logged_in_user(client: AsyncClient, factory: Factory) -> None:
    user = await make_user(factory)
    await log_in(client, user["email"])

    response = await client.get(ME)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user_id"] == user["user_id"]


async def test_me_requires_session(client: AsyncClient) -> None:
    response = await client.get(ME)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_me_rejects_unknown_token(client: AsyncClient) -> None:
    response = await client.get(ME, headers=with_token(security.new_session_token()))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_me_rejects_session_at_expiry(
    client: AsyncClient, factory: Factory
) -> None:
    """고정 시각(T0)이 만료 시각과 같으면 만료다."""
    user = await make_user(factory)
    token = security.new_session_token()
    await factory.user_session(
        user_id=user["user_id"],
        token_hash=security.hash_session_token(token),
        created_at=T0 - security.SESSION_TTL,
        expires_at=T0,
    )

    response = await client.get(ME, headers=with_token(token))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_me_accepts_session_just_before_expiry(
    client: AsyncClient, factory: Factory
) -> None:
    user = await make_user(factory)
    token = security.new_session_token()
    await factory.user_session(
        user_id=user["user_id"],
        token_hash=security.hash_session_token(token),
        created_at=T0 - security.SESSION_TTL,
        expires_at=T0 + timedelta(microseconds=1),
    )

    response = await client.get(ME, headers=with_token(token))

    assert response.status_code == status.HTTP_200_OK


async def test_me_rejects_deactivated_user(
    client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    user = await make_user(factory)
    await log_in(client, user["email"])

    # 세션은 남겨 둔 채 계정만 비활성화해, 매 요청 사용자 상태를 다시 확인하는지 본다.
    await db_session.execute(
        update(User).where(User.user_id == user["user_id"]).values(is_active=False)
    )

    assert (await client.get(ME)).status_code == status.HTTP_401_UNAUTHORIZED


# 로그아웃


async def test_logout_deletes_session_and_clears_cookie(
    client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    user = await make_user(factory)
    token = cookie_value(session_cookie_header(await log_in(client, user["email"])))

    response = await client.post(LOGOUT)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    attributes = cookie_attributes(session_cookie_header(response))
    assert attributes["path"] == SESSION_COOKIE_PATH
    assert attributes["max-age"] == "0"
    remaining = await db_session.scalar(select(func.count()).select_from(UserSession))
    assert remaining == 0
    # 지워진 세션의 토큰을 다시 보내도 거절된다.
    again = await client.get(ME, headers=with_token(token))
    assert again.status_code == status.HTTP_401_UNAUTHORIZED


async def test_logout_requires_session(client: AsyncClient) -> None:
    response = await client.post(LOGOUT)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

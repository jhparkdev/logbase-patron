"""API 테스트 공용 fixture."""

import pytest
from httpx import AsyncClient

from app import security
from tests.db_helpers import Factory

PASSWORD = "correct-password"
# 해시 계산이 느려서(Argon2) 한 번만 만든다.
PASSWORD_HASH = security.hash_password(PASSWORD)
LOGIN_PATH = "/api/auth/login"


@pytest.fixture
async def authed_client(client: AsyncClient, factory: Factory) -> AsyncClient:
    """로그인한 관리자의 HTTP 클라이언트. 받은 세션 쿠키가 다음 요청에 자동으로 실린다."""
    user = await factory.user(password_hash=PASSWORD_HASH)
    response = await client.post(
        LOGIN_PATH, json={"email": user["email"], "password": PASSWORD}
    )
    assert response.status_code == 200
    return client

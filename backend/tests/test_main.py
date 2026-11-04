"""app/main.py 테스트. 실제 앱의 모든 /api 라우트에 인증과 Origin 검사가 걸려 있는지 확인한다.

라우트 목록을 앱에서 직접 읽으므로, 새 라우터를 추가하면 자동으로 이 검사 대상이 된다.
"""

import re

from fastapi import FastAPI, status
from fastapi.routing import APIRoute, iter_route_contexts
from httpx import AsyncClient

from app.config import get_settings
from app.main import API_PREFIX

# 로그인 없이 호출할 수 있는 라우트. 여기에 추가하려면 CLAUDE.md의 예외(로그인·health·기록 API)인지 확인한다.
PUBLIC_ROUTES = {("GET", "/api/health"), ("POST", "/api/auth/login")}
# 기록 API는 브라우저가 아니라 고객 서비스가 부르고 쿠키를 쓰지 않는다. Origin 검사 대신 수신 토큰으로
# 확인한다(CLAUDE.md). 여기에 추가하려면 같은 이유인지 확인하고, 토큰 검사가 있는지 시험한다.
INGEST_ROUTES = {("POST", "/api/usage-records")}
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
FOREIGN_ORIGIN = "https://evil.example"
PATH_PARAMETER = re.compile(r"\{[^}]+\}")


def api_routes(app: FastAPI) -> list[tuple[str, str]]:
    """앱에 등록된 /api 라우트의 (메서드, 경로) 목록.

    FastAPI 0.162부터 include_router로 넣은 라우트는 app.routes에 펼쳐지지 않으므로,
    OpenAPI 생성과 같은 iter_route_contexts로 실제 경로를 읽는다(문서에서 숨긴 라우트도 포함).
    """
    return sorted(
        (method, context.path)
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
        and context.path is not None
        and context.path.startswith(API_PREFIX)
        for method in context.methods or ()
    )


def concrete_path(path: str) -> str:
    """경로 변수({id} 등)를 임의 값으로 채운다. 인증 검사가 값 검증보다 먼저 거절해야 한다."""
    return PATH_PARAMETER.sub("1", path)


async def test_api_routes_use_common_error_format(client: AsyncClient) -> None:
    response = await client.get("/api/no-such-route")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"


# 인증


# Origin 검사


async def test_state_changing_routes_reject_foreign_origin(
    app: FastAPI, client: AsyncClient
) -> None:
    targets = [
        (method, path)
        for method, path in api_routes(app)
        if method in STATE_CHANGING_METHODS and (method, path) not in INGEST_ROUTES
    ]
    assert targets

    for method, path in targets:
        response = await client.request(
            method, concrete_path(path), headers={"Origin": FOREIGN_ORIGIN}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, (method, path)
        assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"


async def test_ingest_routes_check_the_token_instead_of_origin(
    app: FastAPI, client: AsyncClient
) -> None:
    """기록 API는 Origin 검사를 하지 않는 대신, 토큰이 없으면 Origin과 관계없이 401이다."""
    assert INGEST_ROUTES <= set(api_routes(app))

    for method, path in INGEST_ROUTES:
        response = await client.request(
            method, path, json={}, headers={"Origin": FOREIGN_ORIGIN}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (method, path)
        assert response.json()["code"] == "UNAUTHENTICATED"


async def test_state_changing_request_without_origin_is_rejected(
    client: AsyncClient,
) -> None:
    request = client.build_request("POST", "/api/auth/login", json={})
    del request.headers["Origin"]

    response = await client.send(request)

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_read_request_does_not_need_origin(client: AsyncClient) -> None:
    request = client.build_request("GET", "/api/health")
    del request.headers["Origin"]

    response = await client.send(request)

    assert response.status_code == status.HTTP_200_OK


async def test_all_state_changing_requests_are_rejected_without_setting(
    app: FastAPI, client: AsyncClient
) -> None:
    """ALLOWED_ORIGIN을 설정하지 않은 배포에서는 열어 두지 않고 막는다."""
    test_settings = app.dependency_overrides[get_settings]()
    settings = test_settings.model_copy(update={"allowed_origin": None})
    app.dependency_overrides[get_settings] = lambda: settings

    response = await client.post("/api/auth/login", json={})

    assert response.status_code == status.HTTP_403_FORBIDDEN

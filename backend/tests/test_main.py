"""app/main.py 테스트. 실제 앱의 모든 /api 라우트에 인증과 Origin 검사가 걸려 있는지 확인한다.

라우트 목록을 앱에서 직접 읽으므로, 새 라우터를 추가하면 자동으로 이 검사 대상이 된다.
"""

import re

from fastapi import FastAPI, status
from fastapi.routing import APIRoute, iter_route_contexts
from httpx import AsyncClient

from app.config import get_settings
from app.main import API_PREFIX
from tests.api.test_auth import make_user
from tests.db_helpers import Factory

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


async def test_only_public_routes_skip_login(
    app: FastAPI, client: AsyncClient, factory: Factory
) -> None:
    """세션 없이 401이 아닌 응답을 주는 라우트는 공개 목록과 정확히 같아야 한다."""
    # 활성 계정이 있어도 세션이 없으면 거절해야 한다. 계정이 없어서 거절되는 경우와 구분한다
    await make_user(factory)
    reachable_without_login: set[tuple[str, str]] = set()
    for method, path in api_routes(app):
        # 기록 API는 세션 대신 수신 토큰으로 거절한다. 토큰 검사는 test_usage_records.py 에서 본다
        if (method, path) in INGEST_ROUTES:
            continue
        response = await client.request(method, concrete_path(path))
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            assert response.json()["code"] == "UNAUTHENTICATED", (method, path)
        else:
            # 공개 로그인은 본문이 없으면 422다. 성공 여부 대신 세션 요구 여부를 비교한다.
            reachable_without_login.add((method, path))

    assert reachable_without_login == PUBLIC_ROUTES


def test_login_and_validation_errors_are_documented_as_code_and_message(
    app: FastAPI,
) -> None:
    """로그인이 필요한 라우트의 401·422 문서는 실제 응답 형식({code, message})과 같아야 한다.

    프론트엔드 타입이 이 문서에서 생성되므로, FastAPI 기본 형식({detail})이 남으면 타입이 실제와 달라진다.
    """
    document = app.openapi()
    schemas = document["components"]["schemas"]
    skipped = PUBLIC_ROUTES | INGEST_ROUTES
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            if (method.upper(), path) in skipped:
                continue
            responses = operation["responses"]
            assert "401" in responses, (method, path)
            for code in ("401", "422"):
                if code not in responses:
                    continue
                schema = responses[code]["content"]["application/json"]["schema"]
                # 오류 형식이 여러 개면 anyOf 로 적힌다. 하나하나가 {code, message} 여야 한다
                for option in schema.get("anyOf", [schema]):
                    target = schemas[option["$ref"].rsplit("/", 1)[-1]]
                    assert set(target["properties"]) == {"code", "message"}, (
                        method,
                        path,
                        code,
                    )


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

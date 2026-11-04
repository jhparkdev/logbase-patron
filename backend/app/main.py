"""FastAPI 앱 생성과 라우터 등록.

개발 서버: uv --directory backend run fastapi dev app/main.py
"""

from fastapi import Depends, FastAPI

from app.api import (
    assistant,
    auth,
    command_code,
    health,
    internal_budget,
    model_favorites,
    models,
    projects,
    simulation_scenarios,
    simulations,
    subscriptions,
    usage,
    usage_records,
)
from app.api.deps import get_current_user, require_allowed_origin
from app.api.errors import install_error_handlers
from app.schemas.common import ErrorResponse

# 배포 환경에서는 nginx가 /api/* 만 backend로 넘기므로 모든 라우트를 이 아래에 둔다.
API_PREFIX = "/api"
# 로그인 없이 부를 수 있는 라우터. CLAUDE.md의 예외(로그인·health·기록 API)만 둔다.
PUBLIC_ROUTERS = (health.router, auth.public_router)
# 로그인 세션이 있어야 부를 수 있는 기능 라우터. 새 기능 라우터는 여기에 추가한다.
# (기록 API는 쿠키 대신 Ingest 토큰을 쓰므로 Origin 검사와 로그인 검사 없이 따로 등록한다.)
PROTECTED_ROUTERS = (
    assistant.router,
    auth.router,
    simulations.router,
    models.router,
    usage.router,
    model_favorites.router,
    internal_budget.router,
    command_code.router,
    subscriptions.router,
    projects.router,
    simulation_scenarios.router,
)
# 로그인 검사(401)와 형식 검증(422)의 실제 응답 형식. 세션 쿠키를 읽으므로 받는 값이 없는 라우트에도
# FastAPI 가 422 를 기본 형식({detail})으로 적는다. 라우트에 따로 적은 응답이 있으면 그쪽이 우선한다.
PROTECTED_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def create_app() -> FastAPI:
    """앱을 새로 만든다. 테스트는 앱마다 dependency_overrides를 따로 두려고 매번 새로 만든다."""
    app = FastAPI(title="BASE Patron API")
    install_error_handlers(app)
    # Origin 검사를 인증보다 먼저 해, 다른 사이트에서 온 요청은 세션을 조회하지 않고 거절한다.
    origin_check = Depends(require_allowed_origin)
    # 공개 라우트인 로그인도 쿠키를 발급하므로 Origin 검사는 똑같이 적용한다.
    for router in PUBLIC_ROUTERS:
        app.include_router(router, prefix=API_PREFIX, dependencies=[origin_check])
    for router in PROTECTED_ROUTERS:
        app.include_router(
            router,
            prefix=API_PREFIX,
            dependencies=[origin_check, Depends(get_current_user)],
            responses=PROTECTED_RESPONSES,
        )
    # 기록 수신 API는 브라우저가 아니라 고객 서비스가 부른다. Origin 헤더도 쿠키도 없어서
    # Origin 검사와 로그인 검사를 하지 않고, 수신 토큰 헤더로만 확인한다(라우터 안에서).
    app.include_router(usage_records.router, prefix=API_PREFIX)
    return app


app = create_app()

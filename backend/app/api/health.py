"""health 확인. 로그인 없이 호출할 수 있는 경로다."""

from fastapi import APIRouter

from app.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health")
async def read_health() -> HealthRead:
    return HealthRead(status="ok")

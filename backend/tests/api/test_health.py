"""app/api/health.py 테스트."""

from fastapi import status
from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}

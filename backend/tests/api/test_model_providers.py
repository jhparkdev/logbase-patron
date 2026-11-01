"""GET /api/models/providers 테스트. 모델 목록 화면의 제공사 선택 상자에 쓸 선택지를 확인한다."""

from fastapi import status
from httpx import AsyncClient

from tests.db_helpers import Factory

PROVIDERS = "/api/models/providers"


async def test_등록한_모델이_없으면_빈_목록이다(client: AsyncClient) -> None:
    # /providers가 /{model_id}에 걸려 422가 되지 않고 이 경로로 연결되는지도 함께 확인한다.
    response = await client.get(PROVIDERS)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"items": []}


async def test_제공사별_모델_개수를_이름순으로_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(provider="openai")
    await factory.model(provider="openai")
    await factory.model(provider="anthropic")

    body = (await client.get(PROVIDERS)).json()

    assert body == {
        "items": [
            {"provider": "anthropic", "model_count": 1},
            {"provider": "openai", "model_count": 2},
        ]
    }


async def test_모델_상태와_상관없이_모두_센다(
    client: AsyncClient, factory: Factory
) -> None:
    for model_status in ("TESTING", "ACTIVE", "INACTIVE"):
        await factory.model(provider="vendor", status=model_status)

    body = (await client.get(PROVIDERS)).json()

    assert body["items"] == [{"provider": "vendor", "model_count": 3}]

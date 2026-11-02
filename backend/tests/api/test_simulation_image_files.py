"""GET /api/simulations/images/{asset_id} 테스트.

화면이 입력 이미지를 <img> 로 그릴 수 있게 파일 내용을 그대로 내려 준다.
"""

import uuid

import pytest
from httpx import AsyncClient, Response

from app.services.image_storage import LocalImageStorage
from tests.image_samples import png

IMAGES = "/api/simulations/images"


def assert_not_found(response: Response) -> None:
    assert response.status_code == 404
    assert response.json()["code"] == "IMAGE_FILE_NOT_FOUND"


@pytest.mark.usefixtures("signed_in")
async def test_an_uploaded_image_is_served_with_its_type(
    client: AsyncClient, image_storage: LocalImageStorage
) -> None:
    data = png(300)
    uploaded = await client.post(IMAGES, files={"file": ("a.png", data, "image/png")})

    response = await client.get(f"{IMAGES}/{uploaded.json()['asset_id']}")

    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.usefixtures("image_storage")
async def test_an_unknown_uploaded_image_is_404(client: AsyncClient) -> None:
    assert_not_found(await client.get(f"{IMAGES}/{uuid.uuid4()}"))


@pytest.mark.usefixtures("image_storage")
async def test_the_limits_route_is_not_taken_for_an_image_id(
    client: AsyncClient,
) -> None:
    response = await client.get(f"{IMAGES}/limits")

    assert response.status_code == 200
    assert "max_count" in response.json()

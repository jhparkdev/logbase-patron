"""GET /api/simulations/images/{asset_id}, GET /api/simulations/output-images/{output_asset_id} 테스트.

화면이 입력 이미지와 생성 결과 이미지를 <img> 로 그릴 수 있게 파일 내용을 그대로 내려 준다.
"""

import hashlib
import uuid

import pytest
from httpx import AsyncClient, Response

from app.services.image_storage import LocalImageStorage
from tests.db_helpers import Factory
from tests.image_samples import png, webp

IMAGES = "/api/simulations/images"
OUTPUT_IMAGES = "/api/simulations/output-images"


async def stored_output(
    factory: Factory, storage: LocalImageStorage, data: bytes, mime_type: str
) -> uuid.UUID:
    row = await factory.output_asset(
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type=mime_type,
        file_size_bytes=len(data),
    )
    await storage.write(row["storage_path"], data)
    return row["output_asset_id"]


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


async def test_an_output_image_is_served_with_its_type(
    client: AsyncClient, factory: Factory, image_storage: LocalImageStorage
) -> None:
    data = webp(90)
    output_asset_id = await stored_output(factory, image_storage, data, "image/webp")

    response = await client.get(f"{OUTPUT_IMAGES}/{output_asset_id}")

    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["x-content-type-options"] == "nosniff"
    # 결과 이미지는 덮어쓰지 않으므로 같은 주소의 내용이 바뀌지 않는다
    assert "immutable" in response.headers["cache-control"]
    assert "private" in response.headers["cache-control"]


async def test_an_output_image_of_unknown_format_is_not_served_as_an_image(
    client: AsyncClient, factory: Factory, image_storage: LocalImageStorage
) -> None:
    data = b"<svg onload=alert(1)>"
    output_asset_id = await stored_output(
        factory, image_storage, data, "application/octet-stream"
    )

    response = await client.get(f"{OUTPUT_IMAGES}/{output_asset_id}")

    assert response.headers["content-type"] == "application/octet-stream"
    assert "sandbox" in response.headers["content-security-policy"]


@pytest.mark.usefixtures("image_storage")
async def test_an_unknown_output_image_is_404(client: AsyncClient) -> None:
    assert_not_found(await client.get(f"{OUTPUT_IMAGES}/{uuid.uuid4()}"))


async def test_an_output_image_whose_file_is_gone_is_404(
    client: AsyncClient, factory: Factory, image_storage: LocalImageStorage
) -> None:
    row = await factory.output_asset()

    assert_not_found(await client.get(f"{OUTPUT_IMAGES}/{row['output_asset_id']}"))


@pytest.mark.usefixtures("image_storage")
async def test_a_malformed_output_image_id_is_422(client: AsyncClient) -> None:
    assert (await client.get(f"{OUTPUT_IMAGES}/not-a-uuid")).status_code == 422

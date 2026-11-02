"""시뮬레이터 이미지 업로드와 읽기. 검사한 파일을 저장소에 쓰고 DB(input_assets)에는 경로·해시만 남긴다."""

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InputAsset
from app.schemas.simulation_image import ImageMimeType
from app.services.image_storage import ImageStorage
from app.services.simulation_image_check import check_image
from app.services.simulation_image_source import (
    StoredImage,
    StoredImageNotFoundError,
    read_stored,
)

# 저장 키의 폴더. 키는 버킷·루트 없는 상대 경로라 로컬 폴더와 GCS 에서 같은 값이 통한다
STORAGE_FOLDER = "simulator"
MAX_FILENAME_LENGTH = 255
_EXTENSIONS = {
    ImageMimeType.JPEG: ".jpg",
    ImageMimeType.PNG: ".png",
    ImageMimeType.WEBP: ".webp",
}


def storage_key(asset_id: uuid.UUID, mime: ImageMimeType) -> str:
    """저장 키는 asset_id 와 형식으로만 만든다. 사용자가 올린 이름은 경로에 쓰지 않는다."""
    return f"{STORAGE_FOLDER}/{asset_id}{_EXTENSIONS[mime]}"


def clean_filename(filename: str | None) -> str | None:
    """올린 이름에서 폴더 부분을 떼고 길이를 줄인다. 화면에 보여 줄 라벨로만 쓴다."""
    if filename is None:
        return None
    name = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    return name[:MAX_FILENAME_LENGTH] or None


async def save_image(
    session: AsyncSession,
    storage: ImageStorage,
    *,
    data: bytes,
    filename: str | None,
    uploaded_by: int,
    asset_id: uuid.UUID,
) -> InputAsset:
    """이미지를 검사해 저장소에 쓰고 input_assets 행을 만든다. commit 은 부르는 쪽이 한다.

    검사에 실패하면 아무것도 남기지 않는다. 파일을 먼저 쓰고 행을 만들므로, 행을 만들다 실패해도
    남는 것은 아무도 가리키지 않는 파일뿐이다(없는 파일을 가리키는 행은 생기지 않는다).
    """
    mime = check_image(data)
    key = storage_key(asset_id, mime)
    await storage.write(key, data)
    asset = InputAsset(
        asset_id=asset_id,
        storage_path=key,
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type=mime.value,
        file_size_bytes=len(data),
        original_filename=clean_filename(filename),
        uploaded_by=uploaded_by,
    )
    session.add(asset)
    await session.flush()
    return asset


async def read_input_image(
    session: AsyncSession, storage: ImageStorage, asset_id: uuid.UUID
) -> StoredImage:
    """올린 이미지를 읽는다. 이력·재실행 화면이 입력 이미지를 다시 보여 줄 때 쓴다."""
    asset = await session.get(InputAsset, asset_id)
    if asset is None:
        raise StoredImageNotFoundError
    return await read_stored(storage, asset.storage_path, asset.sha256, asset.mime_type)

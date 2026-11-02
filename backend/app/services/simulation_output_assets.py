"""이미지 생성 결과 저장과 읽기. 파일은 저장소에 두고 DB(output_assets)에는 경로·해시만 남긴다.

결과 이미지는 삭제하거나 덮어쓰지 않는다. 키는 새 ID 로만 만들고 저장소도 같은 키를 거절한다.
"""

import hashlib
import uuid
from collections.abc import Callable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import OutputAsset
from app.openrouter.image_result import GeneratedImage
from app.schemas.simulation_image import ImageMimeType
from app.services.image_storage import ImageStorage
from app.services.simulation_assets import STORAGE_FOLDER
from app.services.simulation_image_check import detect_image_mime
from app.services.simulation_image_source import (
    StoredImage,
    StoredImageNotFoundError,
    read_stored,
)

OUTPUT_FOLDER = f"{STORAGE_FOLDER}/output"
# 머리 바이트로 알 수 없는 형식. 응답이 알려 준 형식(예: image/svg+xml)은 믿지 않고 그림으로 내보내지 않는다
UNKNOWN_IMAGE_TYPE = "application/octet-stream"
_UNKNOWN_EXTENSION = ".bin"
_EXTENSIONS = {
    ImageMimeType.JPEG: ".jpg",
    ImageMimeType.PNG: ".png",
    ImageMimeType.WEBP: ".webp",
}


async def save_output_images(
    session: AsyncSession,
    storage: ImageStorage,
    request_id: uuid.UUID,
    images: Sequence[GeneratedImage],
    *,
    new_id: Callable[[], uuid.UUID],
) -> None:
    """받은 순서대로 파일을 쓰고 output_assets 행을 만든다. commit 은 부르는 쪽이 한다.

    파일을 먼저 쓰므로, 행을 만들다 실패해도 없는 파일을 가리키는 행은 생기지 않는다.
    """
    for sort_order, image in enumerate(images):
        output_asset_id = new_id()
        mime = detect_image_mime(image.data)
        extension = _EXTENSIONS[mime] if mime else _UNKNOWN_EXTENSION
        key = f"{OUTPUT_FOLDER}/{output_asset_id}{extension}"
        await storage.write(key, image.data)
        session.add(
            OutputAsset(
                output_asset_id=output_asset_id,
                request_id=request_id,
                sort_order=sort_order,
                storage_path=key,
                sha256=hashlib.sha256(image.data).hexdigest(),
                mime_type=mime.value if mime else UNKNOWN_IMAGE_TYPE,
                file_size_bytes=len(image.data),
            )
        )
    await session.flush()


async def read_output_image(
    session: AsyncSession, storage: ImageStorage, output_asset_id: uuid.UUID
) -> StoredImage:
    asset = await session.get(OutputAsset, output_asset_id)
    if asset is None:
        raise StoredImageNotFoundError
    return await read_stored(storage, asset.storage_path, asset.sha256, asset.mime_type)


class ScopedOutputImageStore:
    """OutputImageStore 포트의 DB 구현. 칸마다 새 세션을 열고 commit 한다(여러 칸이 동시에 저장한다)."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        storage: ImageStorage,
        new_id: Callable[[], uuid.UUID] = uuid.uuid7,
    ) -> None:
        self._sessions = sessions
        self._storage = storage
        self._new_id = new_id

    async def save(
        self, request_id: uuid.UUID, images: Sequence[GeneratedImage]
    ) -> None:
        async with self._sessions.begin() as session:
            await save_output_images(
                session, self._storage, request_id, images, new_id=self._new_id
            )

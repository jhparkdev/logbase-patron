"""저장된 이미지를 모델에 보낼 모양(base64 data URL)으로 읽는다. ImageSource 포트의 저장소 구현."""

import base64
import hashlib
import logging
from dataclasses import dataclass

from app.services.image_storage import ImageNotStoredError, ImageStorage
from app.services.simulation_ports import ImageRef

# 로그에는 저장 키만 남긴다. 키는 ID 로 만든 경로라 그림 내용이나 사용자 정보가 없다
logger = logging.getLogger(__name__)


class ImageIntegrityError(RuntimeError):
    """저장소의 파일이 DB 에 기록된 해시와 다르다. 다른 파일을 입력으로 보내지 않는다."""


async def read_verified(storage: ImageStorage, key: str, sha256: str) -> bytes:
    """저장소에서 읽고, DB 에 기록된 해시와 같을 때만 돌려준다."""
    data = await storage.read(key)
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ImageIntegrityError
    return data


class StoredImageNotFoundError(LookupError):
    """요청한 이미지의 기록이나 파일이 없다."""


@dataclass(frozen=True)
class StoredImage:
    """저장소에서 읽어 해시를 확인한 이미지."""

    data: bytes
    mime_type: str


async def read_stored(
    storage: ImageStorage, key: str, sha256: str, mime_type: str
) -> StoredImage:
    """화면에 내려 줄 이미지를 읽는다. 파일이 없거나 기록과 다르면 기록이 없는 것과 같게 본다.

    기록과 다른 파일은 내려 주지 않는다. 화면에는 없는 그림과 같게 보이고, 원인은 서버 로그에 남긴다.
    """
    try:
        data = await read_verified(storage, key, sha256)
    except ImageNotStoredError as error:
        raise StoredImageNotFoundError from error
    except ImageIntegrityError as error:
        logger.error("stored image does not match its recorded hash: key=%s", key)
        raise StoredImageNotFoundError from error
    return StoredImage(data=data, mime_type=mime_type)


class StorageImageSource:
    def __init__(self, storage: ImageStorage) -> None:
        self._storage = storage

    async def data_url(self, image: ImageRef) -> str:
        data = await read_verified(self._storage, image.storage_path, image.sha256)
        return f"data:{image.mime_type};base64,{base64.b64encode(data).decode()}"

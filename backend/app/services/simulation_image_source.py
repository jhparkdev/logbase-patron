"""저장된 이미지를 모델에 보낼 모양(base64 data URL)으로 읽는다. ImageSource 포트의 저장소 구현."""

import base64
import hashlib
from dataclasses import dataclass

from app.services.image_storage import ImageNotStoredError, ImageStorage
from app.services.simulation_ports import ImageRef


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
    """화면에 내려 줄 이미지를 읽는다. 파일이 없으면 기록이 없는 것과 같게 본다."""
    try:
        data = await read_verified(storage, key, sha256)
    except ImageNotStoredError as error:
        raise StoredImageNotFoundError from error
    return StoredImage(data=data, mime_type=mime_type)


class StorageImageSource:
    def __init__(self, storage: ImageStorage) -> None:
        self._storage = storage

    async def data_url(self, image: ImageRef) -> str:
        data = await read_verified(self._storage, image.storage_path, image.sha256)
        return f"data:{image.mime_type};base64,{base64.b64encode(data).decode()}"

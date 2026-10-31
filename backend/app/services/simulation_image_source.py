"""저장된 이미지를 모델에 보낼 모양(base64 data URL)으로 읽는다. ImageSource 포트의 저장소 구현."""

import base64
import hashlib

from app.services.image_storage import ImageStorage
from app.services.simulation_ports import ImageRef


class ImageIntegrityError(RuntimeError):
    """저장소의 파일이 DB 에 기록된 해시와 다르다. 다른 파일을 입력으로 보내지 않는다."""


class StorageImageSource:
    def __init__(self, storage: ImageStorage) -> None:
        self._storage = storage

    async def data_url(self, image: ImageRef) -> str:
        data = await self._storage.read(image.storage_path)
        if hashlib.sha256(data).hexdigest() != image.sha256:
            raise ImageIntegrityError
        return f"data:{image.mime_type};base64,{base64.b64encode(data).decode()}"

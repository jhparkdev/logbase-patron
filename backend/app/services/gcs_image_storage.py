"""GCS 버킷에 저장하는 이미지 저장소. 배포 환경용이다.

버킷 객체는 바깥에서 받는다. 배포에서는 Cloud Run 서비스 계정의 기본 자격증명으로 만든 버킷을,
테스트에서는 가짜 버킷을 넣는다. 키 파일이나 비밀값은 쓰지 않는다.
"""

import asyncio
from typing import Protocol

from google.api_core.exceptions import NotFound, PreconditionFailed

from app.services.image_storage import (
    ImageNotStoredError,
    UnsafeStorageKeyError,
    check_key,
)

# 앱은 저장된 바이트를 읽어 기록된 mime_type 으로 내보내므로 객체 자체의 형식은 쓰지 않는다
STORED_CONTENT_TYPE = "application/octet-stream"
# "아직 없는 객체일 때만 쓴다"는 GCS 조건. 덮어쓰기를 서버 쪽에서 막는다
ONLY_IF_ABSENT = 0


class Blob(Protocol):
    def upload_from_string(
        self, data: bytes, content_type: str, if_generation_match: int | None
    ) -> None: ...

    def download_as_bytes(self) -> bytes: ...

    def exists(self) -> bool: ...


class Bucket(Protocol):
    def blob(self, name: str) -> Blob: ...


class GcsImageStorage:
    def __init__(self, bucket: Bucket) -> None:
        self._bucket = bucket

    async def write(self, key: str, data: bytes) -> None:
        check_key(key)
        blob = self._bucket.blob(key)
        try:
            await asyncio.to_thread(
                blob.upload_from_string,
                data,
                content_type=STORED_CONTENT_TYPE,
                if_generation_match=ONLY_IF_ABSENT,
            )
        except PreconditionFailed as error:
            raise FileExistsError(key) from error

    async def read(self, key: str) -> bytes:
        check_key(key)
        try:
            return await asyncio.to_thread(self._bucket.blob(key).download_as_bytes)
        except NotFound as error:
            raise ImageNotStoredError from error

    async def exists(self, key: str) -> bool:
        try:
            check_key(key)
        except UnsafeStorageKeyError:
            return False
        return await asyncio.to_thread(self._bucket.blob(key).exists)

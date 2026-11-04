"""이미지 파일 저장소. DB 에는 이 저장소의 키(경로)만 남기고 파일 내용은 여기에 둔다.

로컬 폴더 구현은 여기에, GCS 구현은 gcs_image_storage.py 에 있고 설정에서 바꿔 끼운다. 키는 버킷·폴더 이름 없이 'simulator/<asset_id>.png' 같은 상대 경로라서
어느 구현에서도 같은 값을 쓴다.
"""

import asyncio
from pathlib import Path
from typing import Protocol


class UnsafeStorageKeyError(ValueError):
    """저장소 밖을 가리킬 수 있는 키다(절대 경로, '..', 역슬래시, NUL 등)."""


class ImageNotStoredError(LookupError):
    """키에 해당하는 파일이 저장소에 없다."""


class ImageStorage(Protocol):
    async def write(self, key: str, data: bytes) -> None:
        """새 파일을 쓴다. 같은 키가 이미 있으면 FileExistsError 로 거절한다(덮어쓰지 않는다)."""
        ...

    async def read(self, key: str) -> bytes: ...

    async def exists(self, key: str) -> bool:
        """있으면 True. 안전하지 않은 키도 예외 없이 False 다."""
        ...


def check_key(key: str) -> None:
    """모든 구현이 같은 키 규칙을 쓴다. 저장소를 바꿔 끼워도 같은 기록을 받아야 하기 때문이다."""
    parts = key.replace("\\", "/").split("/")
    if (
        not key
        or "\x00" in key
        or "\\" in key
        or key.startswith("/")
        or ":" in parts[0]
        or ".." in parts
    ):
        raise UnsafeStorageKeyError


class LocalImageStorage:
    """로컬 폴더에 저장한다. 개발과 테스트용이다. Cloud Run 의 디스크는 임시라서 배포에는 쓰지 않는다."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _resolve(self, key: str) -> Path:
        # 문자열 검사로 빠른 거절, 해석된 실제 경로 검사로 심볼릭 링크 우회까지 막는다
        check_key(key)
        root = self._root.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise UnsafeStorageKeyError
        return path

    async def write(self, key: str, data: bytes) -> None:
        path = self._resolve(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as file:
                file.write(data)

        await asyncio.to_thread(_write)

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as error:
            raise ImageNotStoredError from error

    async def exists(self, key: str) -> bool:
        try:
            path = self._resolve(key)
        except UnsafeStorageKeyError:
            return False
        return await asyncio.to_thread(path.is_file)

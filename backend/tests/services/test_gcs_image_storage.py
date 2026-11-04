import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from app.services.gcs_image_storage import GcsImageStorage
from app.services.image_storage import ImageNotStoredError, UnsafeStorageKeyError


class FakeBlob:
    """google.cloud.storage.Blob 중 저장소가 쓰는 부분만 흉내 낸다."""

    def __init__(self, objects: dict[str, bytes], name: str) -> None:
        self._objects = objects
        self._name = name

    def upload_from_string(
        self, data: bytes, content_type: str, if_generation_match: int | None
    ) -> None:
        # 실제 GCS 처럼 generation 0 조건은 "아직 없는 객체일 때만" 이다
        if if_generation_match == 0 and self._name in self._objects:
            raise PreconditionFailed("exists")
        self._objects[self._name] = data

    def download_as_bytes(self) -> bytes:
        try:
            return self._objects[self._name]
        except KeyError:
            raise NotFound("missing") from None

    def exists(self) -> bool:
        return self._name in self._objects


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.requested: list[str] = []

    def blob(self, name: str) -> FakeBlob:
        self.requested.append(name)
        return FakeBlob(self.objects, name)


async def test_written_bytes_can_be_read_back() -> None:
    bucket = FakeBucket()
    storage = GcsImageStorage(bucket)

    await storage.write("simulator/a.png", b"abc")

    assert bucket.objects == {"simulator/a.png": b"abc"}
    assert await storage.read("simulator/a.png") == b"abc"
    assert await storage.exists("simulator/a.png") is True


async def test_a_missing_object_is_reported_not_raised_by_exists() -> None:
    storage = GcsImageStorage(FakeBucket())

    assert await storage.exists("simulator/none.png") is False
    with pytest.raises(ImageNotStoredError):
        await storage.read("simulator/none.png")


async def test_a_stored_object_is_never_overwritten() -> None:
    # 입력 이미지는 이력이다. 같은 키로 다시 쓰면 과거 실행의 입력이 바뀐다
    bucket = FakeBucket()
    storage = GcsImageStorage(bucket)
    await storage.write("simulator/a.png", b"first")

    with pytest.raises(FileExistsError):
        await storage.write("simulator/a.png", b"second")

    assert bucket.objects["simulator/a.png"] == b"first"


@pytest.mark.parametrize(
    "key",
    [
        "../outside.png",
        "simulator/../../outside.png",
        "/etc/passwd",
        "C:\\windows\\x.png",
        "simulator\\..\\x.png",
        "",
        "simulator/\x00.png",
    ],
)
async def test_an_unsafe_key_is_refused_before_reaching_the_bucket(key: str) -> None:
    # 로컬 저장소와 같은 키 규칙을 써야 저장소를 바꿔 끼워도 같은 기록을 받는다
    bucket = FakeBucket()
    storage = GcsImageStorage(bucket)

    with pytest.raises(UnsafeStorageKeyError):
        await storage.write(key, b"x")
    with pytest.raises(UnsafeStorageKeyError):
        await storage.read(key)
    assert await storage.exists(key) is False
    assert bucket.requested == []

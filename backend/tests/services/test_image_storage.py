from pathlib import Path

import pytest

from app.services.image_storage import (
    ImageNotStoredError,
    LocalImageStorage,
    UnsafeStorageKeyError,
)


async def test_written_bytes_can_be_read_back(tmp_path: Path) -> None:
    storage = LocalImageStorage(tmp_path)

    await storage.write("simulator/a.png", b"abc")

    assert await storage.read("simulator/a.png") == b"abc"
    assert await storage.exists("simulator/a.png") is True


async def test_a_missing_file_is_reported_not_raised_by_exists(
    tmp_path: Path,
) -> None:
    storage = LocalImageStorage(tmp_path)

    assert await storage.exists("simulator/none.png") is False
    with pytest.raises(ImageNotStoredError):
        await storage.read("simulator/none.png")


async def test_a_stored_file_is_never_overwritten(tmp_path: Path) -> None:
    # 입력 이미지는 이력이다. 같은 키로 다시 쓰면 과거 실행의 입력이 바뀐다
    storage = LocalImageStorage(tmp_path)
    await storage.write("simulator/a.png", b"first")

    with pytest.raises(FileExistsError):
        await storage.write("simulator/a.png", b"second")

    assert await storage.read("simulator/a.png") == b"first"


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
async def test_a_key_that_leaves_the_storage_root_is_refused(
    tmp_path: Path, key: str
) -> None:
    storage = LocalImageStorage(tmp_path / "root")

    with pytest.raises(UnsafeStorageKeyError):
        await storage.write(key, b"x")
    with pytest.raises(UnsafeStorageKeyError):
        await storage.read(key)
    # 확인용 질문에는 예외 없이 "없다"로 답한다. 옛 seed 처럼 절대 경로가 들어 있는 기록도 안전하게 다룬다
    assert await storage.exists(key) is False
    assert not (tmp_path / "outside.png").exists()


async def test_a_symlink_pointing_outside_the_root_is_refused(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(b"secret")
    (root / "link").symlink_to(outside)
    storage = LocalImageStorage(root)

    with pytest.raises(UnsafeStorageKeyError):
        await storage.read("link/secret.png")

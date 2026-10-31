import base64
import hashlib
import uuid
from pathlib import Path

import pytest

from app.services.image_storage import ImageNotStoredError, LocalImageStorage
from app.services.simulation_image_source import (
    ImageIntegrityError,
    StorageImageSource,
)
from app.services.simulation_ports import ImageRef
from tests.image_samples import png


def ref_for(data: bytes, key: str = "simulator/a.png") -> ImageRef:
    return ImageRef(
        asset_id=uuid.UUID(int=1),
        storage_path=key,
        mime_type="image/png",
        sha256=hashlib.sha256(data).hexdigest(),
    )


async def test_the_stored_file_becomes_a_base64_data_url(tmp_path: Path) -> None:
    storage = LocalImageStorage(tmp_path)
    data = png(100)
    await storage.write("simulator/a.png", data)

    url = await StorageImageSource(storage).data_url(ref_for(data))

    assert url == "data:image/png;base64," + base64.b64encode(data).decode()


async def test_a_file_that_no_longer_matches_its_recorded_hash_is_not_sent(
    tmp_path: Path,
) -> None:
    # 기록된 해시와 다른 파일을 보내면 "그때 그 입력"으로 한 비교가 아니게 된다
    storage = LocalImageStorage(tmp_path)
    await storage.write("simulator/a.png", png(100))

    with pytest.raises(ImageIntegrityError):
        await StorageImageSource(storage).data_url(ref_for(png(200)))


async def test_a_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ImageNotStoredError):
        await StorageImageSource(LocalImageStorage(tmp_path)).data_url(ref_for(png()))

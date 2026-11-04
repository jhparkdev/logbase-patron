"""이미지 생성 결과 저장과 읽기. 파일은 저장소에, DB(output_assets)에는 경로·해시만 남긴다."""

import hashlib
import itertools
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutputAsset
from app.openrouter.image_result import GeneratedImage
from app.services.image_storage import LocalImageStorage
from app.services.simulation_image_source import (
    ImageIntegrityError,
    StoredImageNotFoundError,
)
from app.services.simulation_output_assets import (
    UNKNOWN_IMAGE_TYPE,
    read_output_image,
    save_output_images,
)
from tests.db_helpers import Factory
from tests.image_samples import GIF_HEAD, jpeg, png


def id_maker() -> Callable[[], uuid.UUID]:
    """1, 2, 3 ... 순서로 새 ID 를 낸다."""
    counter = itertools.count(1)
    return lambda: uuid.UUID(int=next(counter))


async def request_id(factory: Factory) -> uuid.UUID:
    return (await factory.ai_request())["request_id"]


async def saved_rows(session: AsyncSession, rid: uuid.UUID) -> list[OutputAsset]:
    return list(
        await session.scalars(
            select(OutputAsset)
            .where(OutputAsset.request_id == rid)
            .order_by(OutputAsset.sort_order)
        )
    )


async def test_each_image_is_stored_with_its_order_path_and_hash(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    storage = LocalImageStorage(tmp_path)
    rid = await request_id(factory)
    first, second = png(100), jpeg(80)

    await save_output_images(
        db_session,
        storage,
        rid,
        [GeneratedImage(data=first), GeneratedImage(data=second)],
        new_id=id_maker(),
    )

    rows = await saved_rows(db_session, rid)
    assert [row.sort_order for row in rows] == [0, 1]
    assert [row.output_asset_id for row in rows] == [uuid.UUID(int=1), uuid.UUID(int=2)]
    assert [row.mime_type for row in rows] == ["image/png", "image/jpeg"]
    assert [row.file_size_bytes for row in rows] == [100, 80]
    assert rows[0].sha256 == hashlib.sha256(first).hexdigest()
    assert rows[0].storage_path == f"simulator/output/{uuid.UUID(int=1)}.png"
    assert rows[1].storage_path == f"simulator/output/{uuid.UUID(int=2)}.jpg"
    assert await storage.read(rows[1].storage_path) == second


async def test_the_type_comes_from_the_content_not_the_reported_media_type(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    # 응답이 알려 준 형식을 믿으면 다른 내용(예: 스크립트가 든 SVG)을 그림처럼 내보내게 된다
    rid = await request_id(factory)

    await save_output_images(
        db_session,
        LocalImageStorage(tmp_path),
        rid,
        [GeneratedImage(data=png(), media_type="image/svg+xml")],
        new_id=uuid.uuid4,
    )

    [row] = await saved_rows(db_session, rid)
    assert row.mime_type == "image/png"


async def test_an_unrecognised_format_is_kept_as_opaque_bytes(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    # 비용이 나간 결과라 버리지 않는다. 화면이 그림으로 해석하지 않게 형식만 감춘다
    storage = LocalImageStorage(tmp_path)
    rid = await request_id(factory)
    data = GIF_HEAD + b"\x00" * 10

    await save_output_images(
        db_session, storage, rid, [GeneratedImage(data=data)], new_id=uuid.uuid4
    )

    [row] = await saved_rows(db_session, rid)
    assert row.mime_type == UNKNOWN_IMAGE_TYPE
    assert row.storage_path.endswith(".bin")
    assert await storage.read(row.storage_path) == data


class FailingSecondWrite(LocalImageStorage):
    """두 번째 파일부터 쓰지 못하는 저장소(디스크가 가득 찬 경우)."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes = 0

    async def write(self, key: str, data: bytes) -> None:
        self.writes += 1
        if self.writes > 1:
            raise OSError("disk full")
        await super().write(key, data)


async def test_a_failed_save_keeps_written_files_and_logs_where_they_are(
    db_session: AsyncSession,
    factory: Factory,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 비용이 나간 결과라 지우지 않는다. 기록 없이 남은 파일을 나중에 찾을 수 있게 로그에 남긴다
    storage = FailingSecondWrite(tmp_path)
    rid = await request_id(factory)
    first_key = f"simulator/output/{uuid.UUID(int=1)}.png"

    with pytest.raises(OSError):
        await save_output_images(
            db_session,
            storage,
            rid,
            [GeneratedImage(data=png()), GeneratedImage(data=png())],
            new_id=id_maker(),
        )

    assert await storage.read(first_key) == png()
    assert str(rid) in caplog.text
    assert first_key in caplog.text


async def test_a_stored_output_image_is_read_back_with_its_type(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    storage = LocalImageStorage(tmp_path)
    rid = await request_id(factory)
    data = png(50)
    await save_output_images(
        db_session,
        storage,
        rid,
        [GeneratedImage(data=data)],
        new_id=id_maker(),
    )

    image = await read_output_image(db_session, storage, uuid.UUID(int=1))

    assert (image.data, image.mime_type) == (data, "image/png")


async def test_an_unknown_output_image_is_not_found(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    with pytest.raises(StoredImageNotFoundError):
        await read_output_image(db_session, LocalImageStorage(tmp_path), uuid.uuid4())


async def test_an_output_image_whose_file_is_gone_is_not_found(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    row = await factory.output_asset()

    with pytest.raises(StoredImageNotFoundError):
        await read_output_image(
            db_session, LocalImageStorage(tmp_path), row["output_asset_id"]
        )


async def test_an_output_image_whose_file_was_changed_is_not_served(
    db_session: AsyncSession,
    factory: Factory,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 화면에는 없는 그림과 같게 보이고, 바뀐 파일은 운영자가 찾을 수 있게 로그에 남긴다
    storage = LocalImageStorage(tmp_path)
    row = await factory.output_asset()  # 해시는 0 으로 채운 값이다
    await storage.write(row["storage_path"], png())

    with pytest.raises(StoredImageNotFoundError) as raised:
        await read_output_image(db_session, storage, row["output_asset_id"])

    assert isinstance(raised.value.__cause__, ImageIntegrityError)
    assert row["storage_path"] in caplog.text

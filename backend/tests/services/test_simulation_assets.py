import hashlib
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InputAsset
from app.services.image_storage import LocalImageStorage
from app.services.simulation_assets import read_input_image, save_image
from app.services.simulation_image_check import UnsupportedImageTypeError
from app.services.simulation_image_source import StoredImageNotFoundError
from tests.db_helpers import Factory
from tests.image_samples import jpeg, png

ASSET_ID = uuid.UUID("0192a3c4-0000-7000-8000-0000000000a1")


async def user_id(factory: Factory) -> int:
    return int((await factory.user())["user_id"])


async def asset_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(InputAsset)) or 0


async def test_a_saved_image_keeps_its_path_and_hash_in_the_database(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    storage = LocalImageStorage(tmp_path)
    data = png(200)

    asset = await save_image(
        db_session,
        storage,
        data=data,
        filename="dress.png",
        uploaded_by=await user_id(factory),
        asset_id=ASSET_ID,
    )

    row = await db_session.get(InputAsset, ASSET_ID)
    assert row is not None and row is asset
    assert row.storage_path == f"simulator/{ASSET_ID}.png"
    assert row.sha256 == hashlib.sha256(data).hexdigest()
    assert row.mime_type == "image/png"
    assert row.file_size_bytes == 200
    assert row.original_filename == "dress.png"
    # 파일 내용은 저장소에만 있고 DB 에는 없다
    assert await storage.read(row.storage_path) == data


async def test_the_type_is_taken_from_the_content_not_the_file_name(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    asset = await save_image(
        db_session,
        LocalImageStorage(tmp_path),
        data=jpeg(),
        filename="actually-a-jpeg.png",
        uploaded_by=await user_id(factory),
        asset_id=ASSET_ID,
    )

    assert asset.mime_type == "image/jpeg"
    assert asset.storage_path == f"simulator/{ASSET_ID}.jpg"


@pytest.mark.parametrize(
    "given, kept",
    [
        ("../../etc/passwd.png", "passwd.png"),
        ("C:\\Users\\me\\photo.png", "photo.png"),
        ("  spaced.png  ", "spaced.png"),
        ("", None),
        (None, None),
        ("a" * 300 + ".png", ("a" * 300 + ".png")[:255]),
    ],
)
async def test_the_original_file_name_is_only_a_label(
    db_session: AsyncSession,
    factory: Factory,
    tmp_path: Path,
    given: str | None,
    kept: str | None,
) -> None:
    # 저장 경로는 asset_id 로만 만든다. 올린 이름이 경로에 섞이지 않고 라벨로만 남는다
    asset = await save_image(
        db_session,
        LocalImageStorage(tmp_path),
        data=png(),
        filename=given,
        uploaded_by=await user_id(factory),
        asset_id=ASSET_ID,
    )

    assert asset.original_filename == kept
    assert asset.storage_path == f"simulator/{ASSET_ID}.png"


async def test_a_rejected_image_leaves_no_row_and_no_file(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    with pytest.raises(UnsupportedImageTypeError):
        await save_image(
            db_session,
            LocalImageStorage(tmp_path),
            data=b"not an image",
            filename="x.png",
            uploaded_by=await user_id(factory),
            asset_id=ASSET_ID,
        )

    assert await asset_count(db_session) == 0
    assert list(tmp_path.rglob("*")) == []


async def test_an_uploaded_image_is_read_back_with_its_type(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    storage = LocalImageStorage(tmp_path)
    data = jpeg(120)
    await save_image(
        db_session,
        storage,
        data=data,
        filename="a.jpg",
        uploaded_by=await user_id(factory),
        asset_id=ASSET_ID,
    )

    image = await read_input_image(db_session, storage, ASSET_ID)

    assert (image.data, image.mime_type) == (data, "image/jpeg")


async def test_an_unknown_uploaded_image_is_not_found(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    with pytest.raises(StoredImageNotFoundError):
        await read_input_image(db_session, LocalImageStorage(tmp_path), uuid.uuid4())


async def test_an_uploaded_image_whose_file_is_gone_is_not_found(
    db_session: AsyncSession, factory: Factory, tmp_path: Path
) -> None:
    row = await factory.input_asset()

    with pytest.raises(StoredImageNotFoundError):
        await read_input_image(db_session, LocalImageStorage(tmp_path), row["asset_id"])

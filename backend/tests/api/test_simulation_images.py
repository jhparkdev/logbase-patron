"""POST /api/simulations/images, GET /api/simulations/images/limits 테스트.

올린 파일의 형식·크기 경계와 저장 결과(DB에는 경로·해시만, 내용은 저장소에)를 확인한다.
"""

import hashlib
import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InputAsset, SimulationRun, SimulationRunAsset
from app.schemas.simulation_image import MAX_IMAGE_BYTES, MAX_IMAGE_COUNT
from app.services.image_storage import LocalImageStorage
from tests.api.simulation_helpers import FakeManager, count, create_body
from tests.api.test_auth import log_in, make_user
from tests.db_helpers import Factory
from tests.image_samples import GIF_HEAD, jpeg, png

IMAGES = "/api/simulations/images"


async def upload(
    client: AsyncClient,
    data: bytes,
    filename: str = "dress.png",
    content_type: str = "image/png",
) -> Response:
    return await client.post(IMAGES, files={"file": (filename, data, content_type)})


async def stored_rows(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(InputAsset)) or 0


@pytest.mark.usefixtures("signed_in")
async def test_an_uploaded_image_answers_201_with_its_id_and_keeps_no_bytes_in_the_db(
    client: AsyncClient,
    db_session: AsyncSession,
    image_storage: LocalImageStorage,
) -> None:
    data = png(300)

    response = await upload(client, data)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "asset_id",
        "mime_type",
        "file_size_bytes",
        "original_filename",
    }
    assert body["mime_type"] == "image/png"
    assert body["file_size_bytes"] == 300
    assert body["original_filename"] == "dress.png"
    row = await db_session.get(InputAsset, uuid.UUID(body["asset_id"]))
    assert row is not None
    assert row.sha256 == hashlib.sha256(data).hexdigest()
    assert await image_storage.read(row.storage_path) == data


@pytest.mark.usefixtures("signed_in")
async def test_the_uploader_is_recorded(
    client: AsyncClient,
    db_session: AsyncSession,
    image_storage: LocalImageStorage,
) -> None:
    response = await upload(client, png())

    row = await db_session.get(InputAsset, uuid.UUID(response.json()["asset_id"]))
    assert row is not None and row.uploaded_by is not None


@pytest.mark.usefixtures("image_storage")
async def test_the_uploader_is_the_signed_in_account_not_the_first_one(
    client: AsyncClient, db_session: AsyncSession, factory: Factory
) -> None:
    await make_user(factory)
    user = await make_user(factory)
    await log_in(client, user["email"])

    response = await upload(client, png())

    row = await db_session.get(InputAsset, uuid.UUID(response.json()["asset_id"]))
    assert row is not None
    assert row.uploaded_by == user["user_id"]


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_a_file_exactly_at_the_size_limit_is_accepted(
    client: AsyncClient,
) -> None:
    assert (await upload(client, png(MAX_IMAGE_BYTES))).status_code == 201


@pytest.mark.usefixtures("signed_in")
async def test_a_file_just_over_the_size_limit_is_refused_and_not_stored(
    client: AsyncClient,
    db_session: AsyncSession,
    image_storage: LocalImageStorage,
) -> None:
    response = await upload(client, png(MAX_IMAGE_BYTES + 1))

    assert response.status_code == 413
    assert response.json()["code"] == "IMAGE_TOO_LARGE"
    assert await stored_rows(db_session) == 0


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_an_empty_file_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await upload(client, b"")

    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_EMPTY"
    assert await stored_rows(db_session) == 0


@pytest.mark.usefixtures("signed_in", "image_storage")
@pytest.mark.parametrize(
    "data, filename, content_type",
    [
        (GIF_HEAD + b"\x00" * 16, "a.gif", "image/gif"),
        (
            b"MZ\x90\x00 executable",
            "innocent.png",
            "image/png",
        ),  # 이름·형식 선언은 믿지 않는다
        (b"<svg></svg>", "a.svg", "image/svg+xml"),
    ],
)
async def test_other_content_is_refused_with_a_message_for_the_user(
    client: AsyncClient,
    db_session: AsyncSession,
    data: bytes,
    filename: str,
    content_type: str,
) -> None:
    response = await upload(client, data, filename, content_type)

    assert response.status_code == 415
    body = response.json()
    assert body["code"] == "IMAGE_TYPE_NOT_SUPPORTED"
    assert "JPG" in body["message"]
    assert await stored_rows(db_session) == 0


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_a_request_without_a_file_is_a_validation_error(
    client: AsyncClient,
) -> None:
    response = await client.post(IMAGES, data={"note": "no file"})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_an_upload_from_another_origin_is_refused(client: AsyncClient) -> None:
    response = await client.post(
        IMAGES,
        files={"file": ("a.png", png(), "image/png")},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_the_same_file_uploaded_twice_gets_two_separate_assets(
    client: AsyncClient,
) -> None:
    # 입력 이미지는 이력이다. 내용이 같아도 실행마다 따로 남겨 한쪽을 바꿔도 다른 실행이 영향받지 않는다
    first = (await upload(client, png())).json()["asset_id"]
    second = (await upload(client, png())).json()["asset_id"]

    assert first != second


@pytest.mark.usefixtures("signed_in")
async def test_the_limits_endpoint_serves_the_policy_values(
    client: AsyncClient,
) -> None:
    response = await client.get(f"{IMAGES}/limits")

    assert response.status_code == 200
    assert response.json() == {
        "max_count": MAX_IMAGE_COUNT,
        "max_bytes": MAX_IMAGE_BYTES,
        "mime_types": ["image/jpeg", "image/png", "image/webp"],
    }


# --- 업로드한 이미지로 비교 실행을 접수한다 ---

RUNS = "/api/simulations"


async def accepted_run_assets(session: AsyncSession, simulation_id: str) -> list[str]:
    rows = await session.execute(
        select(SimulationRunAsset.asset_id)
        .where(SimulationRunAsset.simulation_id == uuid.UUID(simulation_id))
        .order_by(SimulationRunAsset.sort_order)
    )
    return [str(asset_id) for (asset_id,) in rows]


async def image_models(factory: Factory, *, second_supports_images: bool) -> list[int]:
    first = await factory.model(status="ACTIVE", input_modalities=["text", "image"])
    second = await factory.model(
        status="ACTIVE",
        input_modalities=["text", "image"] if second_supports_images else ["text"],
    )
    return [first["model_id"], second["model_id"]]


@pytest.mark.usefixtures("poc_setup", "signed_in", "image_storage")
async def test_a_run_with_uploaded_images_is_accepted_and_keeps_their_order(
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
    manager: FakeManager,
) -> None:
    models = await image_models(factory, second_supports_images=True)
    first = (await upload(client, png(), "a.png")).json()["asset_id"]
    second = (await upload(client, jpeg(), "b.jpg")).json()["asset_id"]

    response = await client.post(
        RUNS, json=create_body(models, asset_ids=[second, first])
    )

    assert response.status_code == 202
    assert await accepted_run_assets(db_session, response.json()["simulation_id"]) == [
        second,
        first,
    ]
    [job] = manager.jobs
    assert [str(image.asset_id) for image in job.images] == [second, first]


@pytest.mark.usefixtures("poc_setup", "signed_in", "image_storage")
async def test_an_image_that_was_never_uploaded_is_refused_and_nothing_is_saved(
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
    manager: FakeManager,
) -> None:
    models = await image_models(factory, second_supports_images=True)

    response = await client.post(
        RUNS, json=create_body(models, asset_ids=[str(uuid.uuid4())])
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_NOT_FOUND"
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0


@pytest.mark.usefixtures("poc_setup", "signed_in", "image_storage")
async def test_an_image_whose_file_is_gone_is_refused_and_no_run_is_made(
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
    manager: FakeManager,
) -> None:
    # 기록은 남았지만 저장소에서 파일이 사라졌다. 실행을 만들면 모든 칸이 실패로 영구히 남는다
    models = await image_models(factory, second_supports_images=True)
    kept = (await upload(client, png())).json()["asset_id"]
    gone = await factory.input_asset(storage_path="simulator/vanished.png")

    response = await client.post(
        RUNS, json=create_body(models, asset_ids=[kept, str(gone["asset_id"])])
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_NOT_FOUND"
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0


@pytest.mark.usefixtures("poc_setup", "signed_in", "image_storage")
async def test_a_model_that_cannot_read_images_is_refused_before_any_cost(
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
    manager: FakeManager,
) -> None:
    models = await image_models(factory, second_supports_images=False)
    asset = (await upload(client, png())).json()["asset_id"]

    response = await client.post(RUNS, json=create_body(models, asset_ids=[asset]))

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_IMAGE_NOT_SUPPORTED"
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0


@pytest.mark.usefixtures("poc_setup", "signed_in", "image_storage", "manager")
async def test_more_images_than_the_limit_is_a_validation_error(
    client: AsyncClient, factory: Factory
) -> None:
    models = await image_models(factory, second_supports_images=True)

    response = await client.post(
        RUNS,
        json=create_body(
            models, asset_ids=[str(uuid.uuid4()) for _ in range(MAX_IMAGE_COUNT + 1)]
        ),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.usefixtures("poc_setup", "signed_in", "image_storage")
async def test_the_rerun_draft_of_an_image_run_goes_back_as_a_new_request(
    client: AsyncClient, factory: Factory, manager: FakeManager
) -> None:
    models = await image_models(factory, second_supports_images=True)
    asset = (await upload(client, png())).json()["asset_id"]
    first = await client.post(RUNS, json=create_body(models, asset_ids=[asset]))
    simulation_id = first.json()["simulation_id"]

    draft = (await client.get(f"{RUNS}/{simulation_id}/rerun-draft")).json()
    assert (draft["rerunnable"], draft["asset_ids"]) == (True, [asset])
    new_request = {
        key: value
        for key, value in draft.items()
        if key not in {"rerunnable", "blocked_reason", "images"}
    }
    new_request["models"] = [
        {
            k: v
            for k, v in model.items()
            if k in {"model_id", "execution_provider", "execution_config"}
        }
        for model in draft["models"]
    ]
    again = await client.post(RUNS, json=new_request)

    assert again.status_code == 202
    assert again.json()["simulation_id"] != simulation_id
    assert [str(image.asset_id) for image in manager.jobs[-1].images] == [asset]

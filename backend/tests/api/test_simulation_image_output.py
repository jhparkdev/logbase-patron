"""이미지 생성 실행을 접수부터 결과 조회·파일 내려받기까지 실제 DB 로 확인한다. 모델 호출만 가짜다."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.simulation_deps import get_simulation_manager
from app.openrouter.image_result import ImageCallResult
from app.services.image_storage import LocalImageStorage
from app.services.simulation_output_assets import ScopedOutputImageStore
from tests.api.simulation_helpers import (
    CREATE,
    build_manager,
    build_sessions,
    create_body,
)
from tests.db_helpers import Factory
from tests.services.simulation_fakes import FakeCaller, FakeImageGenerator, image_ok

IMAGE_OPTIONS = {"n": 2, "aspect_ratio": "1:1", "quality": "low"}


async def image_models(factory: Factory) -> list[dict[str, Any]]:
    return [
        dict(
            await factory.model(
                status="ACTIVE", output_modalities=["image"], input_modalities=["text"]
            )
        )
        for _ in range(2)
    ]


async def run_image_simulation(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalImageStorage,
    rows: list[dict[str, Any]],
    generator: FakeImageGenerator,
) -> str:
    sessions = build_sessions(db_session)
    manager = build_manager(
        db_session,
        caller=None,
        sessions=sessions,
        image_generator=generator,
        outputs=ScopedOutputImageStore(sessions, storage),  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_simulation_manager] = lambda: manager
    response = await client.post(
        CREATE,
        json=create_body(
            [row["model_id"] for row in rows],
            output_type="IMAGE",
            image_config=IMAGE_OPTIONS,
        ),
    )
    assert response.status_code == 202, response.json()
    await manager.wait_idle()
    return response.json()["simulation_id"]


def returning(result: ImageCallResult) -> Any:
    async def behavior(kwargs: dict[str, Any]) -> ImageCallResult:
        return result

    return behavior


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_an_image_run_shows_each_slots_images_and_serves_their_files(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
    image_storage: LocalImageStorage,
) -> None:
    rows = await image_models(factory)
    two_images = image_ok(count=2)
    generator = FakeImageGenerator(
        {rows[0]["openrouter_model_id"]: returning(two_images)}
    )

    simulation_id = await run_image_simulation(
        app, client, db_session, image_storage, rows, generator
    )
    body = (await client.get(f"{CREATE}/{simulation_id}")).json()

    assert body["summary"]["status"] == "SUCCESS"
    first, second = body["results"]
    assert first["output_type"] == second["output_type"] == "IMAGE"
    assert first["execution_config"] == {"output_type": "IMAGE", **IMAGE_OPTIONS}
    assert first["response_text"] is None
    assert Decimal(first["cost_usd"]) == Decimal("0.04")
    assert [image["sort_order"] for image in first["output_images"]] == [0, 1]
    assert len(second["output_images"]) == 1
    for image, sent in zip(first["output_images"], two_images.images, strict=True):
        assert image["mime_type"] == "image/png"
        assert image["file_size_bytes"] == len(sent.data)
        served = await client.get(f"{CREATE}/output-images/{image['output_asset_id']}")
        assert served.content == sent.data


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_a_text_run_has_no_output_images(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
) -> None:
    rows = [dict(await factory.model(status="ACTIVE")) for _ in range(2)]
    manager = build_manager(db_session, FakeCaller())
    app.dependency_overrides[get_simulation_manager] = lambda: manager
    response = await client.post(
        CREATE, json=create_body([row["model_id"] for row in rows])
    )
    await manager.wait_idle()

    body = (await client.get(f"{CREATE}/{response.json()['simulation_id']}")).json()

    for result in body["results"]:
        assert (result["output_type"], result["output_images"]) == ("TEXT", [])


@pytest.mark.usefixtures("poc_setup", "signed_in", "manager")
async def test_an_image_run_with_a_model_that_cannot_make_images_is_422(
    client: AsyncClient, factory: Factory
) -> None:
    rows = [
        dict(await factory.model(status="ACTIVE", output_modalities=["image"])),
        dict(await factory.model(status="ACTIVE", output_modalities=["text"])),
    ]

    response = await client.post(
        CREATE,
        json=create_body([row["model_id"] for row in rows], output_type="IMAGE"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_IMAGE_OUTPUT_NOT_SUPPORTED"


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        # 취소 뒤 늦게 도착한 결과는 대조용으로만 남기고 결과로 보여 주지 않는다
        ("CANCELLED", None),
        # 그림을 저장한 뒤 결과를 기록하기 전에 서버가 멈추면, 정리 작업이 칸을 실패로 끝낸다
        ("FAILED", "UNKNOWN_ERROR"),
    ],
)
@pytest.mark.usefixtures("image_storage")
async def test_images_of_a_slot_that_did_not_succeed_are_not_shown(
    client: AsyncClient, factory: Factory, status: str, error_type: str | None
) -> None:
    run = await factory.simulation_run(execution_config={"output_type": "IMAGE"})
    request = await factory.ai_request(
        usage_origin="SIMULATION",
        simulation_id=run["simulation_id"],
        status=status,
        error_type=error_type,
        execution_config={"output_type": "IMAGE"},
    )
    await factory.simulation_result(
        simulation_id=run["simulation_id"], request_id=request["request_id"]
    )
    await factory.output_asset(request_id=request["request_id"])

    body = (await client.get(f"{CREATE}/{run['simulation_id']}")).json()

    [result] = body["results"]
    assert result["status"] == status
    assert result["output_images"] == []

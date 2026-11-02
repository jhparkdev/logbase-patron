"""GET /api/simulations/{id}/rerun-draft (S-09) 테스트. 과거 실행의 입력으로 화면 입력칸을 채운다."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SimulationRun
from app.services.image_storage import LocalImageStorage
from tests.api.simulation_helpers import CREATE, FakeManager, create_body
from tests.db_helpers import Factory
from tests.image_samples import png

SCHEMA = {"type": "object", "required": ["title"]}
# 초안에서 화면 안내에만 쓰고 새 실행 요청에는 싣지 않는 값과 모델 칸의 현재 상태
GUIDANCE_FIELDS = {"rerunnable", "blocked_reason", "images"}
CURRENT_MODEL_FIELDS = {"current_display_name", "current_status", "selectable"}


def draft_url(simulation_id: object) -> str:
    return f"{CREATE}/{simulation_id}/rerun-draft"


def as_new_request(draft: dict[str, Any]) -> dict[str, Any]:
    """화면이 하는 일: 초안에서 안내용 값을 빼고 그대로 새 실행으로 보낸다."""
    body = {k: v for k, v in draft.items() if k not in GUIDANCE_FIELDS}
    body["models"] = [
        {k: v for k, v in model.items() if k not in CURRENT_MODEL_FIELDS}
        for model in draft["models"]
    ]
    return body


async def past_run_id(client: AsyncClient, models: list[int]) -> str:
    body = create_body(
        models,
        prompt_text="  상품 설명을 써 주세요\n",
        input_text="상품: 텀블러",
        json_schema=SCHEMA,
        routing_policy={"allow_fallbacks": True},
    )
    response = await client.post(CREATE, json=body)
    assert response.status_code == 202, response.text
    return response.json()["simulation_id"]


@pytest.mark.usefixtures("signed_in")
async def test_an_unknown_run_has_no_draft(client: AsyncClient) -> None:
    response = await client.get(draft_url(uuid.uuid7()))

    assert response.status_code == 404
    assert response.json()["code"] == "SIMULATION_NOT_FOUND"


@pytest.mark.usefixtures("poc_setup", "signed_in", "manager")
async def test_the_draft_returns_what_was_run(
    client: AsyncClient, models: list[int]
) -> None:
    simulation_id = await past_run_id(client, models)

    response = await client.get(draft_url(simulation_id))

    assert response.status_code == 200
    draft = response.json()
    assert draft["rerun_of_simulation_id"] == simulation_id
    assert draft["prompt_text"] == "  상품 설명을 써 주세요\n"
    assert draft["input_text"] == "상품: 텀블러"
    assert draft["json_schema"] == SCHEMA
    # 실행 당시 실제로 쓴 설정이다(보내지 않은 최대 토큰은 기본값으로 기록되었다)
    assert draft["execution_config"] == {"max_tokens": 4096}
    assert draft["routing_policy"] == {"allow_fallbacks": True}
    assert [(m["model_id"], m["execution_provider"]) for m in draft["models"]] == [
        (models[0], "DeepInfra"),
        (models[1], "DekaLLM"),
    ]
    assert (draft["rerunnable"], draft["blocked_reason"]) == (True, None)


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_the_draft_sent_back_starts_a_new_run_pointing_to_the_old_one(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
) -> None:
    # 초안과 새 실행 요청의 모양이 어긋나면 화면은 초안을 그대로 보낼 수 없다
    simulation_id = await past_run_id(client, models)
    draft = (await client.get(draft_url(simulation_id))).json()

    response = await client.post(CREATE, json=as_new_request(draft))

    assert response.status_code == 202, response.text
    new_id = response.json()["simulation_id"]
    assert new_id != simulation_id
    new_run = await db_session.get(SimulationRun, uuid.UUID(new_id))
    assert new_run is not None
    assert str(new_run.rerun_of_simulation_id) == simulation_id
    assert new_run.prompt_text == "  상품 설명을 써 주세요\n"
    assert len(manager.jobs) == 2


@pytest.mark.usefixtures("poc_setup", "signed_in", "manager")
async def test_a_model_deactivated_since_shows_its_current_state(
    client: AsyncClient, models: list[int], db_session: AsyncSession
) -> None:
    simulation_id = await past_run_id(client, models)
    await db_session.execute(
        text(
            "UPDATE models SET status = 'INACTIVE', display_name = '새 이름' "
            "WHERE model_id = :model_id"
        ),
        {"model_id": models[1]},
    )

    draft = (await client.get(draft_url(simulation_id))).json()

    inactive = draft["models"][1]
    assert (inactive["current_status"], inactive["selectable"]) == ("INACTIVE", False)
    assert inactive["current_display_name"] == "새 이름"
    assert draft["models"][0]["selectable"] is True
    # 교체·제외하면 되므로 재실행 자체는 막지 않는다
    assert draft["rerunnable"] is True


@pytest.mark.usefixtures("signed_in")
async def test_only_the_final_attempt_of_each_slot_is_offered(
    client: AsyncClient, factory: Factory
) -> None:
    run = await factory.simulation_run()
    retired = await factory.model()
    final = [await factory.model() for _ in range(2)]
    simulation_id = run["simulation_id"]
    await factory.simulation_result(
        simulation_id=simulation_id,
        slot_no=1,
        model_id=retired["model_id"],
        is_final_attempt=False,
    )
    for slot_no, model in enumerate(final, start=1):
        await factory.simulation_result(
            simulation_id=simulation_id, slot_no=slot_no, model_id=model["model_id"]
        )

    draft = (await client.get(draft_url(simulation_id))).json()

    assert [m["model_id"] for m in draft["models"]] == [m["model_id"] for m in final]


async def run_with_images(
    factory: Factory, *paths: str, filenames: list[str | None] | None = None
) -> tuple[Any, list[str]]:
    run = await factory.simulation_run()
    simulation_id = run["simulation_id"]
    for slot_no in (1, 2):
        await factory.simulation_result(simulation_id=simulation_id, slot_no=slot_no)
    asset_ids = []
    names = filenames or [None] * len(paths)
    for order, (path, name) in enumerate(zip(paths, names, strict=True), start=1):
        asset = await factory.input_asset(storage_path=path, original_filename=name)
        await factory.simulation_run_asset(
            simulation_id=simulation_id, asset_id=asset["asset_id"], sort_order=order
        )
        asset_ids.append(str(asset["asset_id"]))
    return simulation_id, asset_ids


@pytest.mark.usefixtures("signed_in")
async def test_a_run_whose_image_files_remain_is_offered_with_its_images_in_order(
    client: AsyncClient, factory: Factory, image_storage: LocalImageStorage
) -> None:
    await image_storage.write("simulator/first.png", png())
    await image_storage.write("simulator/second.png", png())
    simulation_id, asset_ids = await run_with_images(
        factory, "simulator/first.png", "simulator/second.png"
    )

    draft = (await client.get(draft_url(simulation_id))).json()

    assert (draft["rerunnable"], draft["blocked_reason"]) == (True, None)
    assert draft["asset_ids"] == asset_ids


@pytest.mark.usefixtures("signed_in")
async def test_the_draft_names_each_image_it_was_run_with(
    client: AsyncClient, factory: Factory, image_storage: LocalImageStorage
) -> None:
    # 상세·재실행 화면이 "이미지 1" 대신 올린 파일 이름을 보여 주게 한다
    await image_storage.write("simulator/front.png", png())
    await image_storage.write("simulator/unnamed.png", png())
    simulation_id, asset_ids = await run_with_images(
        factory,
        "simulator/front.png",
        "simulator/unnamed.png",
        filenames=["앞면.png", None],
    )

    draft = (await client.get(draft_url(simulation_id))).json()

    assert draft["images"] == [
        {
            "asset_id": asset_ids[0],
            "mime_type": "image/png",
            "file_size_bytes": 1,
            "original_filename": "앞면.png",
        },
        {
            "asset_id": asset_ids[1],
            "mime_type": "image/png",
            "file_size_bytes": 1,
            "original_filename": None,
        },
    ]


@pytest.mark.usefixtures("poc_setup", "signed_in", "manager")
async def test_a_text_only_run_has_no_images(
    client: AsyncClient, models: list[int]
) -> None:
    simulation_id = await past_run_id(client, models)

    draft = (await client.get(draft_url(simulation_id))).json()

    assert (draft["asset_ids"], draft["images"]) == ([], [])


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_a_run_whose_image_file_is_gone_is_offered_but_blocked(
    client: AsyncClient, factory: Factory
) -> None:
    simulation_id, asset_ids = await run_with_images(factory, "simulator/vanished.png")

    response = await client.get(draft_url(simulation_id))

    assert response.status_code == 200
    draft = response.json()
    assert (draft["rerunnable"], draft["blocked_reason"]) == (False, "INPUT_MISSING")
    assert draft["asset_ids"] == asset_ids


@pytest.mark.usefixtures("signed_in", "image_storage")
async def test_an_old_record_with_an_absolute_path_is_blocked_not_a_server_error(
    client: AsyncClient, factory: Factory
) -> None:
    # 옛 seed 의 경로(/data/assets/...)는 이 저장소의 키가 아니다. 오류가 아니라 "복원 불가"로 답한다
    simulation_id, _ = await run_with_images(factory, "/data/assets/2026/10/x.jpg")

    draft = (await client.get(draft_url(simulation_id))).json()

    assert (draft["rerunnable"], draft["blocked_reason"]) == (False, "INPUT_MISSING")


@pytest.mark.usefixtures("poc_setup", "signed_in", "manager")
async def test_a_run_with_per_model_settings_can_be_rerun_as_it_was(
    client: AsyncClient, models: list[int]
) -> None:
    body = create_body(
        models,
        models=[
            {
                "model_id": models[0],
                "execution_provider": "DeepInfra",
                "execution_config": {"reasoning_effort": effort, "temperature": 0.2},
            }
            for effort in ("low", "high")
        ],
    )
    created = await client.post(CREATE, json=body)
    assert created.status_code == 202, created.text

    draft = (await client.get(draft_url(created.json()["simulation_id"]))).json()

    assert [m["execution_config"] for m in draft["models"]] == [
        {"max_tokens": 4096, "temperature": 0.2, "reasoning_effort": effort}
        for effort in ("low", "high")
    ]
    # 화면은 초안을 그대로 새 실행으로 보내므로 설정까지 같은 두 칸이 중복으로 걸리지 않아야 한다
    again = await client.post(CREATE, json=as_new_request(draft))
    assert again.status_code == 202, again.text

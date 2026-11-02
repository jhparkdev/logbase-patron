"""이미지 생성 실행의 접수. 이미지를 만드는 모델만 받고, 이미지 옵션을 실행·호출 이력에 남긴다."""

from dataclasses import replace
from typing import Any

import pytest

from app.schemas.simulation import SimulationCreateRequest
from app.schemas.simulation_output import OutputType
from app.services.simulation_create import (
    ModelImageOutputUnsupportedError,
    create_simulation,
)
from tests.services.test_simulation_create import (
    SCENARIO_ID,
    USER_ID,
    Intake,
    custom_request,
    scenario_request,
)

IMAGE_OPTIONS = {"n": 2, "aspect_ratio": "1:1", "resolution": "1K", "quality": "low"}
STORED = {"output_type": "IMAGE", **IMAGE_OPTIONS}


def image_intake() -> Intake:
    intake = Intake()
    for model_id, model in intake.lookup.models.items():
        intake.lookup.models[model_id] = replace(model, generates_images=True)
    return intake


def image_request(**overrides: Any) -> SimulationCreateRequest:
    return custom_request(output_type="IMAGE", image_config=IMAGE_OPTIONS, **overrides)


async def test_the_job_of_an_image_run_says_it_makes_images() -> None:
    intake = image_intake()

    job = await create_simulation(
        image_request(), executed_by=USER_ID, deps=intake.deps
    )

    assert job.output_type == OutputType.IMAGE
    assert job.json_schema is None


async def test_the_image_options_are_recorded_on_the_run_every_request_and_slot() -> (
    None
):
    intake = image_intake()

    job = await create_simulation(
        image_request(), executed_by=USER_ID, deps=intake.deps
    )

    [run] = intake.store.runs
    assert run.execution_config == STORED
    assert [r.execution_config for r in intake.recorder.created] == [STORED, STORED]
    assert [slot.execution_config for slot in job.slots] == [STORED, STORED]


async def test_a_text_run_records_no_output_type() -> None:
    # 예전 기록과 같은 모양을 유지한다. output_type 이 없으면 텍스트 실행이다
    intake = Intake()

    job = await create_simulation(
        custom_request(), executed_by=USER_ID, deps=intake.deps
    )

    assert job.output_type == OutputType.TEXT
    assert "output_type" not in intake.store.runs[0].execution_config


async def test_an_image_scenario_run_drops_the_scenario_text_settings_and_schema() -> (
    None
):
    # 시나리오 기본 Schema·온도·최대 토큰은 이미지 호출에 보내지 않으므로 기록하지도 않는다
    intake = image_intake()
    request = scenario_request(output_type="IMAGE")

    job = await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    [run] = intake.store.runs
    assert run.scenario_id == SCENARIO_ID
    assert run.json_schema is None
    assert run.execution_config == {"output_type": "IMAGE"}
    assert run.routing_policy["require_parameters"] is False
    assert job.json_schema is None


async def test_an_image_run_with_a_model_that_cannot_make_images_is_refused() -> None:
    intake = image_intake()
    intake.lookup.models[2] = replace(intake.lookup.models[2], generates_images=False)

    with pytest.raises(ModelImageOutputUnsupportedError) as error:
        await create_simulation(image_request(), executed_by=USER_ID, deps=intake.deps)

    assert error.value.model_ids == [2]
    assert intake.nothing_was_saved()


async def test_a_text_run_does_not_ask_for_image_making_models() -> None:
    intake = Intake()  # 어느 모델도 이미지를 만들지 않는다

    await create_simulation(custom_request(), executed_by=USER_ID, deps=intake.deps)

    assert len(intake.store.runs) == 1


async def test_the_same_model_and_provider_twice_is_refused_in_an_image_run() -> None:
    # 모든 칸의 이미지 옵션이 같으므로 같은 모델·Provider 두 칸은 같은 비교 대상이다
    intake = image_intake()
    same = {"model_id": 1, "execution_provider": "DeepInfra"}

    with pytest.raises(ValueError):
        await create_simulation(
            image_request(models=[same, same]), executed_by=USER_ID, deps=intake.deps
        )
    assert intake.nothing_was_saved()

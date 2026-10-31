"""이미지가 든 비교 실행의 접수. 올려 둔 이미지를 확인하고, 순서대로 실행에 연결한다."""

import uuid
from dataclasses import replace
from typing import Any

import pytest

from app.models import InputType
from app.schemas.simulation import SimulationCreateRequest
from app.services.simulation_create import (
    ImageNotFoundError,
    ImageRequiredError,
    ModelImageUnsupportedError,
    create_simulation,
)
from app.services.simulation_input import build_messages
from app.services.simulation_ports import ImageRef
from tests.services.simulation_fakes import FakeLookup
from tests.services.test_simulation_create import (
    SCENARIO_ID,
    USER_ID,
    Intake,
    custom_request,
    scenario_request,
)


def image(n: int) -> ImageRef:
    return ImageRef(
        asset_id=uuid.UUID(int=1000 + n),
        storage_path=f"simulator/{n}.png",
        mime_type="image/png",
        sha256=f"{n:064d}",
    )


def with_images(intake: Intake, *numbers: int) -> list[ImageRef]:
    refs = [image(n) for n in numbers]
    intake.lookup.images.update({ref.asset_id: ref for ref in refs})
    return refs


def asset_ids(refs: list[ImageRef]) -> list[str]:
    return [str(ref.asset_id) for ref in refs]


def request_with(refs: list[ImageRef], **overrides: Any) -> SimulationCreateRequest:
    return custom_request(asset_ids=asset_ids(refs), **overrides)


def set_scenario_input(lookup: FakeLookup, input_type: InputType) -> None:
    lookup.scenarios[SCENARIO_ID] = replace(
        lookup.scenarios[SCENARIO_ID], input_type=input_type
    )


async def test_the_job_carries_the_images_in_the_order_the_user_chose() -> None:
    intake = Intake()
    refs = with_images(intake, 2, 1, 3)

    job = await create_simulation(
        request_with(refs), executed_by=USER_ID, deps=intake.deps
    )

    assert list(job.images) == refs
    # DB 에 남는 메시지에는 이미지 내용이 아니라 참조만 있다
    assert job.messages == build_messages("강점을 3가지로 정리하세요.", refs)


async def test_the_images_are_linked_to_the_run_in_order() -> None:
    intake = Intake()
    refs = with_images(intake, 2, 1)

    job = await create_simulation(
        request_with(refs), executed_by=USER_ID, deps=intake.deps
    )

    assert intake.store.run_assets == [
        (job.simulation_id, [ref.asset_id for ref in refs])
    ]


async def test_a_text_only_run_has_no_images_and_no_links() -> None:
    intake = Intake()

    job = await create_simulation(
        custom_request(), executed_by=USER_ID, deps=intake.deps
    )

    assert job.images == ()
    assert intake.store.run_assets == []
    assert job.messages == build_messages("강점을 3가지로 정리하세요.")


async def test_an_asset_that_was_never_uploaded_is_refused_before_anything_is_saved() -> (
    None
):
    intake = Intake()
    [known] = with_images(intake, 1)
    unknown = image(9)

    with pytest.raises(ImageNotFoundError) as caught:
        await create_simulation(
            request_with([known, unknown]), executed_by=USER_ID, deps=intake.deps
        )

    assert caught.value.asset_ids == [unknown.asset_id]
    assert intake.nothing_was_saved()
    assert intake.store.run_assets == []


async def test_a_model_without_image_input_is_refused_before_anything_is_saved() -> (
    None
):
    intake = Intake()
    refs = with_images(intake, 1)
    intake.lookup.models[2] = replace(intake.lookup.models[2], supports_images=False)

    with pytest.raises(ModelImageUnsupportedError) as caught:
        await create_simulation(
            request_with(refs), executed_by=USER_ID, deps=intake.deps
        )

    assert caught.value.model_ids == [2]
    assert intake.nothing_was_saved()


async def test_a_model_without_image_input_is_fine_for_a_text_only_run() -> None:
    intake = Intake()
    intake.lookup.models[2] = replace(intake.lookup.models[2], supports_images=False)

    await create_simulation(custom_request(), executed_by=USER_ID, deps=intake.deps)

    assert len(intake.store.runs) == 1


@pytest.mark.parametrize("input_type", [InputType.IMAGE, InputType.TEXT_IMAGE])
async def test_a_scenario_that_needs_an_image_refuses_a_run_without_one(
    input_type: InputType,
) -> None:
    intake = Intake()
    set_scenario_input(intake.lookup, input_type)

    with pytest.raises(ImageRequiredError):
        await create_simulation(
            scenario_request(), executed_by=USER_ID, deps=intake.deps
        )

    assert intake.nothing_was_saved()


async def test_a_scenario_that_needs_an_image_accepts_a_run_with_one() -> None:
    intake = Intake()
    set_scenario_input(intake.lookup, InputType.IMAGE)
    refs = with_images(intake, 1)

    job = await create_simulation(
        scenario_request(asset_ids=asset_ids(refs)),
        executed_by=USER_ID,
        deps=intake.deps,
    )

    assert list(job.images) == refs


async def test_a_text_scenario_does_not_need_an_image() -> None:
    intake = Intake()
    set_scenario_input(intake.lookup, InputType.TEXT)

    await create_simulation(scenario_request(), executed_by=USER_ID, deps=intake.deps)

    assert len(intake.store.runs) == 1

"""이미지 생성 실행. 칸마다 이미지 생성을 부르고, 받은 그림을 저장한 뒤 결과를 기록한다."""

import asyncio
import uuid
from decimal import Decimal
from typing import Any

from app.models import CostStatus, ErrorType, RequestStatus, SimulationStatus
from app.openrouter.image_result import ImageCallResult
from app.schemas.simulation_output import OutputType
from app.services.simulation_ports import ImageRef
from app.services.simulation_run import run_simulation
from tests.services.simulation_fakes import (
    Harness,
    image_failed,
    image_ok,
)

R = RequestStatus
OPTIONS = {"n": 2, "aspect_ratio": "16:9", "resolution": "2K", "quality": "high"}
IMAGE_CONFIG = {"output_type": "IMAGE", **OPTIONS}
REFERENCE = ImageRef(uuid.UUID(int=21), "simulator/ref.png", "image/png", "c" * 64)


def image_harness(count: int = 2, **kwargs: Any) -> Harness:
    return Harness(
        count=count,
        output_type=OutputType.IMAGE,
        slot_config=IMAGE_CONFIG,
        **kwargs,
    )


def returning(result: ImageCallResult) -> Any:
    async def behavior(kwargs: dict[str, Any]) -> ImageCallResult:
        return result

    return behavior


async def test_every_slot_calls_image_generation_and_never_the_text_model() -> None:
    harness = image_harness(count=3)

    overall = await run_simulation(harness.job, harness.deps)

    assert overall == SimulationStatus.SUCCESS
    assert harness.caller.calls == []
    assert [call["model_id"] for call in harness.image_generator.calls] == [
        harness.model(1),
        harness.model(2),
        harness.model(3),
    ]


async def test_the_call_carries_the_prompt_provider_and_image_options() -> None:
    harness = image_harness(count=1, allow_fallbacks=True)

    await run_simulation(harness.job, harness.deps)

    [call] = harness.image_generator.calls
    assert call["request_id"] == harness.request_id(1)
    assert call["prompt"] == "질문"
    assert call["input_image_urls"] is None
    assert call["provider_order"] == ["Provider1"]
    assert call["allow_fallbacks"] is True
    assert {key: call[key] for key in OPTIONS} == OPTIONS
    assert "output_type" not in call
    assert isinstance(call["cancel"], asyncio.Event)


async def test_uploaded_images_go_as_reference_image_content() -> None:
    harness = image_harness(count=1, images=[REFERENCE])

    await run_simulation(harness.job, harness.deps)

    [call] = harness.image_generator.calls
    assert call["prompt"] == "질문"
    assert call["input_image_urls"] == [
        f"data:image/png;base64,{REFERENCE.asset_id.hex}"
    ]


async def test_the_returned_images_are_saved_for_that_slot_in_order() -> None:
    harness = image_harness(
        count=2, image_behaviors={"vendor/model-1": returning(image_ok(count=2))}
    )

    await run_simulation(harness.job, harness.deps)

    first = harness.outputs.saved[harness.request_id(1)]
    assert [image.data for image in first] == [
        image.data for image in image_ok(count=2).images
    ]
    assert len(harness.outputs.saved[harness.request_id(2)]) == 1


async def test_a_successful_slot_records_tokens_and_confirmed_cost() -> None:
    harness = image_harness(count=1)

    await run_simulation(harness.job, harness.deps)

    record = harness.recorder.records[harness.request_id(1)]
    assert record.status == R.SUCCESS
    assert record.response_text is None
    assert (record.input_tokens, record.output_tokens) == (10, 1290)
    assert (record.cost_status, record.cost_usd) == (
        CostStatus.CONFIRMED,
        Decimal("0.04"),
    )
    # 원문 자리에는 저장용 메시지만 남는다. 그림 내용은 저장소에만 있다
    messages, response_text = harness.recorder.payloads[harness.request_id(1)]
    assert (messages, response_text) == (harness.messages, None)


async def test_a_failed_generation_saves_no_images() -> None:
    harness = image_harness(
        count=2, image_behaviors={"vendor/model-1": returning(image_failed())}
    )

    overall = await run_simulation(harness.job, harness.deps)

    assert overall == SimulationStatus.PARTIAL_SUCCESS
    assert harness.request_id(1) not in harness.outputs.saved
    assert harness.recorder.records[harness.request_id(1)].status == R.FAILED


async def test_images_that_cannot_be_stored_fail_the_slot_but_keep_the_cost() -> None:
    # 그림 없이 성공으로 보이면 안 된다. 비용은 이미 나갔으므로 그대로 남긴다
    harness = image_harness(count=1)
    harness.outputs.failing = True

    overall = await run_simulation(harness.job, harness.deps)

    record = harness.recorder.records[harness.request_id(1)]
    assert overall == SimulationStatus.FAILED
    assert record.status == R.FAILED
    assert record.error_type == ErrorType.UNKNOWN_ERROR
    assert record.error_message
    assert (record.cost_status, record.cost_usd) == (
        CostStatus.CONFIRMED,
        Decimal("0.04"),
    )


async def test_an_exception_from_the_generator_fails_only_that_slot() -> None:
    async def explode(kwargs: dict[str, Any]) -> ImageCallResult:
        raise RuntimeError("예상 밖 오류")

    harness = image_harness(count=2, image_behaviors={"vendor/model-1": explode})

    overall = await run_simulation(harness.job, harness.deps)

    assert overall == SimulationStatus.PARTIAL_SUCCESS
    record = harness.recorder.records[harness.request_id(1)]
    assert (record.status, record.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)


async def test_a_slot_cancelled_while_generating_keeps_the_late_result_only() -> None:
    harness = image_harness(count=1)

    async def cancelled_first(kwargs: dict[str, Any]) -> ImageCallResult:
        await harness.recorder.cancel_if_open(kwargs["request_id"], harness.deps.now())
        return image_ok()

    harness.image_generator.behaviors[harness.model(1)] = cancelled_first

    await run_simulation(harness.job, harness.deps)

    assert harness.recorder.statuses[harness.request_id(1)] == R.CANCELLED
    assert harness.request_id(1) in harness.recorder.late
    assert harness.request_id(1) not in harness.recorder.records


async def test_a_text_run_never_calls_image_generation() -> None:
    harness = Harness(count=2)

    await run_simulation(harness.job, harness.deps)

    assert harness.image_generator.calls == []
    assert harness.outputs.saved == {}

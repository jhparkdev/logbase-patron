"""이미지가 든 실행. 모델에는 이미지 내용을 보내고, DB 에는 참조만 남긴다."""

import uuid

from app.models import SimulationStatus
from app.services.simulation_ports import ImageRef
from app.services.simulation_run import run_simulation
from tests.services.simulation_fakes import Harness

IMAGE_A = ImageRef(uuid.UUID(int=11), "simulator/a.png", "image/png", "a" * 64)
IMAGE_B = ImageRef(uuid.UUID(int=12), "simulator/b.jpg", "image/jpeg", "b" * 64)


def image_urls(messages: list[dict]) -> list[str]:
    return [
        part["image_url"]["url"]
        for part in messages[0]["content"]
        if part["type"] == "image_url"
    ]


async def test_every_model_receives_the_image_content_not_the_reference() -> None:
    harness = Harness(count=3, images=[IMAGE_A, IMAGE_B])

    await run_simulation(harness.job, harness.deps)

    expected = [
        f"data:image/png;base64,{IMAGE_A.asset_id.hex}",
        f"data:image/jpeg;base64,{IMAGE_B.asset_id.hex}",
    ]
    assert len(harness.caller.calls) == 3
    for call in harness.caller.calls:
        assert image_urls(call["messages"]) == expected


async def test_the_saved_payload_keeps_references_and_no_image_content() -> None:
    harness = Harness(count=2, images=[IMAGE_A])

    await run_simulation(harness.job, harness.deps)

    for request_id in (harness.request_id(1), harness.request_id(2)):
        stored_messages, _ = harness.recorder.payloads[request_id]
        assert image_urls(stored_messages) == [f"asset:{IMAGE_A.asset_id}"]
        assert "base64" not in str(stored_messages)


async def test_each_image_is_read_once_per_run_not_once_per_model() -> None:
    harness = Harness(count=4, images=[IMAGE_A, IMAGE_B])

    await run_simulation(harness.job, harness.deps)

    assert sorted(harness.images.loaded) == sorted([IMAGE_A.asset_id, IMAGE_B.asset_id])


async def test_an_unreadable_image_fails_every_slot_without_calling_a_model() -> None:
    # 이미지가 없으면 모델은 질문의 절반만 보게 된다. 비용만 나가고 비교가 의미 없으므로 호출하지 않는다
    harness = Harness(count=2, images=[IMAGE_A])
    harness.images.failing.add(IMAGE_A.asset_id)

    overall = await run_simulation(harness.job, harness.deps)

    assert harness.caller.calls == []
    assert overall == SimulationStatus.FAILED
    for request_id in (harness.request_id(1), harness.request_id(2)):
        assert harness.recorder.records[request_id].error_type is not None


async def test_a_text_only_run_never_touches_the_image_source() -> None:
    harness = Harness(count=2)

    await run_simulation(harness.job, harness.deps)

    assert harness.images.loaded == []
    assert harness.caller.calls[0]["messages"] == harness.messages

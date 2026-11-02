import uuid
from typing import Any

import pytest

from app.models import ModelStatus, SimulationRun
from app.schemas.simulation_history import RerunBlockReason
from app.schemas.simulation_output import ImageConfig, OutputType
from app.services.simulation_rerun import PastSlot, build_rerun_draft

PAST_ID = uuid.UUID("0192a3c4-0000-7000-8000-000000000001")
SCHEMA = {"type": "object", "required": ["title"]}


def past_run(**values: Any) -> SimulationRun:
    """DB 없이 만든 과거 실행 행. 초안은 이 행의 값만 읽는다."""
    fields: dict[str, Any] = {
        "simulation_id": PAST_ID,
        "test_type": "CUSTOM",
        "scenario_id": None,
        "prompt_text": "  상품 설명을 써 주세요\n",
        "input_text": "상품: 텀블러",
        "json_schema": SCHEMA,
        "execution_config": {"max_tokens": 4096},
        "routing_policy": {"allow_fallbacks": True, "require_parameters": True},
    }
    fields.update(values)
    return SimulationRun(**fields)


def slot(
    model_id: int,
    status: ModelStatus = ModelStatus.ACTIVE,
    execution_config: dict[str, Any] | None = None,
) -> PastSlot:
    return PastSlot(
        model_id=model_id,
        execution_provider=f"provider-{model_id}",
        execution_config=execution_config or {"max_tokens": 4096},
        current_display_name=f"모델 {model_id}",
        current_status=status,
    )


SLOTS = [slot(1), slot(2)]


def test_the_draft_restores_the_past_inputs_unchanged() -> None:
    draft = build_rerun_draft(past_run(), SLOTS)

    assert draft.rerun_of_simulation_id == PAST_ID
    assert draft.test_type == "CUSTOM"
    assert draft.scenario_id is None
    # 실행 당시 원문 그대로다. 앞뒤 공백도 다듬지 않는다
    assert draft.prompt_text == "  상품 설명을 써 주세요\n"
    assert draft.input_text == "상품: 텀블러"
    assert draft.json_schema == SCHEMA
    assert draft.execution_config == {"max_tokens": 4096}


def test_a_scenario_run_keeps_its_scenario() -> None:
    run = past_run(test_type="SCENARIO", scenario_id=7)

    draft = build_rerun_draft(run, SLOTS)

    assert (draft.test_type, draft.scenario_id) == ("SCENARIO", 7)


def test_only_the_policy_the_user_chooses_comes_back() -> None:
    # require_parameters 는 서버가 정해 기록한 값이라 사용자가 고칠 칸이 아니다
    draft = build_rerun_draft(past_run(), SLOTS)

    assert draft.routing_policy.model_dump() == {"allow_fallbacks": True}


def test_a_policy_recorded_without_fallbacks_reads_as_no_fallbacks() -> None:
    # 값이 없던 과거 기록은 새 실행의 기본값(업체를 바꾸지 않음)으로 읽는다
    run = past_run(routing_policy={})

    draft = build_rerun_draft(run, SLOTS)

    assert draft.routing_policy.allow_fallbacks is False


def test_models_keep_their_slot_order_and_pinned_provider() -> None:
    draft = build_rerun_draft(past_run(), [slot(2), slot(1)])

    assert [(m.model_id, m.execution_provider) for m in draft.models] == [
        (2, "provider-2"),
        (1, "provider-1"),
    ]


@pytest.mark.parametrize(
    ("status", "selectable"),
    [
        (ModelStatus.ACTIVE, True),
        (ModelStatus.TESTING, False),
        (ModelStatus.INACTIVE, False),
    ],
)
def test_each_model_says_whether_it_can_be_chosen_today(
    status: ModelStatus, selectable: bool
) -> None:
    draft = build_rerun_draft(past_run(), [slot(1), slot(2, status)])

    assert draft.models[1].current_status == status
    assert draft.models[1].selectable is selectable


def test_a_model_that_can_no_longer_be_chosen_does_not_block_the_rerun() -> None:
    # 교체하거나 빼면 되므로 막지 않고 안내만 한다
    slots = [slot(1), slot(2, ModelStatus.INACTIVE)]

    draft = build_rerun_draft(past_run(), slots)

    assert (draft.rerunnable, draft.blocked_reason) == (True, None)


IMAGE_IDS = [uuid.UUID(int=21), uuid.UUID(int=22)]


def test_a_run_with_images_whose_files_remain_can_be_rerun_with_them() -> None:
    draft = build_rerun_draft(past_run(), SLOTS, asset_ids=IMAGE_IDS)

    assert (draft.rerunnable, draft.blocked_reason) == (True, None)
    # 올린 순서가 곧 모델에 보낸 순서다
    assert draft.asset_ids == IMAGE_IDS


def test_a_run_whose_image_files_are_gone_cannot_be_restored() -> None:
    # 다른 이미지로 돌리면 같은 입력의 비교가 아니다
    draft = build_rerun_draft(
        past_run(), SLOTS, asset_ids=IMAGE_IDS, assets_available=False
    )

    assert draft.rerunnable is False
    assert draft.blocked_reason == RerunBlockReason.INPUT_MISSING
    assert draft.asset_ids == IMAGE_IDS


def test_a_text_only_run_has_no_images_to_restore() -> None:
    draft = build_rerun_draft(past_run(), SLOTS, assets_available=False)

    assert (draft.rerunnable, draft.asset_ids) == (True, [])


def test_each_model_comes_back_with_the_settings_that_were_applied() -> None:
    # 칸마다 다르게 돌린 설정을 돌려줘야 같은 조건으로 다시 돌릴 수 있다
    slots = [
        slot(1, execution_config={"max_tokens": 100, "reasoning_effort": "low"}),
        slot(1, execution_config={"max_tokens": 100, "reasoning_effort": "high"}),
    ]

    draft = build_rerun_draft(past_run(), slots)

    assert [m.execution_config for m in draft.models] == [
        {"max_tokens": 100, "reasoning_effort": "low"},
        {"max_tokens": 100, "reasoning_effort": "high"},
    ]


IMAGE_STORED = {"output_type": "IMAGE", "n": 2, "aspect_ratio": "16:9"}


def test_an_image_run_comes_back_as_an_image_request() -> None:
    # 기록된 설정을 요청 모양으로 나눈다. 그대로 돌려주면 새 실행 요청이 모르는 항목으로 거절된다
    run = past_run(json_schema=None, execution_config=IMAGE_STORED)
    slots = [
        slot(1, execution_config=IMAGE_STORED),
        slot(2, execution_config=IMAGE_STORED),
    ]

    draft = build_rerun_draft(run, slots)

    assert draft.output_type == OutputType.IMAGE
    assert draft.image_config == ImageConfig(n=2, aspect_ratio="16:9")
    assert draft.execution_config == {}
    assert [model.execution_config for model in draft.models] == [{}, {}]


def test_a_text_run_comes_back_as_a_text_request() -> None:
    draft = build_rerun_draft(past_run(), SLOTS)

    assert (draft.output_type, draft.image_config) == (OutputType.TEXT, None)
    assert [model.execution_config for model in draft.models] == [
        {"max_tokens": 4096},
        {"max_tokens": 4096},
    ]

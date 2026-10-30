import uuid
from typing import Any

import pytest

from app.models import ModelStatus, SimulationRun
from app.schemas.simulation_history import RerunBlockReason
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


def slot(model_id: int, status: ModelStatus = ModelStatus.ACTIVE) -> PastSlot:
    return PastSlot(
        model_id=model_id,
        execution_provider=f"provider-{model_id}",
        current_display_name=f"모델 {model_id}",
        current_status=status,
    )


SLOTS = [slot(1), slot(2)]


def test_the_draft_restores_the_past_inputs_unchanged() -> None:
    draft = build_rerun_draft(past_run(), SLOTS, has_input_assets=False)

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

    draft = build_rerun_draft(run, SLOTS, has_input_assets=False)

    assert (draft.test_type, draft.scenario_id) == ("SCENARIO", 7)


def test_only_the_policy_the_user_chooses_comes_back() -> None:
    # require_parameters 는 서버가 정해 기록한 값이라 사용자가 고칠 칸이 아니다
    draft = build_rerun_draft(past_run(), SLOTS, has_input_assets=False)

    assert draft.routing_policy.model_dump() == {"allow_fallbacks": True}


def test_a_policy_recorded_without_fallbacks_reads_as_no_fallbacks() -> None:
    # 값이 없던 과거 기록은 새 실행의 기본값(업체를 바꾸지 않음)으로 읽는다
    run = past_run(routing_policy={})

    draft = build_rerun_draft(run, SLOTS, has_input_assets=False)

    assert draft.routing_policy.allow_fallbacks is False


def test_models_keep_their_slot_order_and_pinned_provider() -> None:
    draft = build_rerun_draft(past_run(), [slot(2), slot(1)], has_input_assets=False)

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
    draft = build_rerun_draft(
        past_run(), [slot(1), slot(2, status)], has_input_assets=False
    )

    assert draft.models[1].current_status == status
    assert draft.models[1].selectable is selectable


def test_a_model_that_can_no_longer_be_chosen_does_not_block_the_rerun() -> None:
    # 교체하거나 빼면 되므로 막지 않고 안내만 한다
    slots = [slot(1), slot(2, ModelStatus.INACTIVE)]

    draft = build_rerun_draft(past_run(), slots, has_input_assets=False)

    assert (draft.rerunnable, draft.blocked_reason) == (True, None)


def test_a_run_with_attached_images_cannot_be_restored() -> None:
    # 새 실행 요청에는 이미지 칸이 없어서 같은 입력으로 다시 돌릴 수 없다
    draft = build_rerun_draft(past_run(), SLOTS, has_input_assets=True)

    assert draft.rerunnable is False
    assert draft.blocked_reason == RerunBlockReason.INPUT_MISSING

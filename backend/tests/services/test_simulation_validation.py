from typing import Any

import pytest

from app.models import ModelStatus
from app.services.simulation_validation import (
    MAX_MODEL_COUNT,
    MIN_MODEL_COUNT,
    DuplicateModelSelectionError,
    ModelCountError,
    ModelSelection,
    is_model_selectable,
    validate_model_count,
    validate_model_selection,
)

# models 표의 model_id(숫자)
GPT = 1
CLAUDE = 2


def test_limits_are_two_to_four() -> None:
    assert (MIN_MODEL_COUNT, MAX_MODEL_COUNT) == (2, 4)


# 경계값은 바로 전, 정확히 그 값, 바로 후를 모두 검사한다 (T-19)
@pytest.mark.parametrize("count", [2, 3, 4])
def test_count_within_range_is_accepted(count: int) -> None:
    validate_model_count(count)


@pytest.mark.parametrize("count", [0, 1, 5, 10])
def test_count_outside_range_is_rejected(count: int) -> None:
    with pytest.raises(ModelCountError) as error:
        validate_model_count(count)
    assert error.value.count == count


def test_provider_is_required_for_every_selection() -> None:
    # simulation_results.execution_provider 는 NOT NULL 이다 (자동 라우팅 없음)
    with pytest.raises(TypeError):
        ModelSelection(GPT)  # type: ignore[call-arg]


def test_different_models_are_accepted() -> None:
    validate_model_selection(
        [ModelSelection(GPT, "openai"), ModelSelection(CLAUDE, "anthropic")]
    )


def test_same_model_with_different_providers_is_accepted() -> None:
    # 같은 모델을 Provider 만 바꿔 비교할 수 있다
    validate_model_selection(
        [ModelSelection(GPT, "azure"), ModelSelection(GPT, "openai")]
    )


def test_same_model_with_same_provider_is_rejected() -> None:
    duplicated = ModelSelection(GPT, "openai")
    with pytest.raises(DuplicateModelSelectionError) as error:
        validate_model_selection(
            [ModelSelection(CLAUDE, "anthropic"), duplicated, duplicated]
        )
    assert error.value.selection == duplicated


def test_same_provider_with_different_models_is_accepted() -> None:
    validate_model_selection(
        [ModelSelection(GPT, "openai"), ModelSelection(CLAUDE, "openai")]
    )


def test_four_selections_of_one_model_with_four_providers_are_accepted() -> None:
    providers = ["openai", "azure", "together", "fireworks"]
    validate_model_selection([ModelSelection(GPT, name) for name in providers])


def test_count_is_checked_before_duplicates() -> None:
    # 1개 선택, 5개 선택은 중복 여부와 상관없이 개수 오류가 먼저다 (T-19)
    with pytest.raises(ModelCountError):
        validate_model_selection([ModelSelection(GPT, "openai")])
    five_duplicates = [ModelSelection(GPT, "openai")] * 5
    with pytest.raises(ModelCountError):
        validate_model_selection(five_duplicates)


def test_duplicate_is_found_even_at_the_upper_limit() -> None:
    selections = [
        ModelSelection(GPT, "openai"),
        ModelSelection(CLAUDE, "anthropic"),
        ModelSelection(GPT, "azure"),
        ModelSelection(CLAUDE, "anthropic"),
    ]
    with pytest.raises(DuplicateModelSelectionError) as error:
        validate_model_selection(selections)
    assert error.value.selection == ModelSelection(CLAUDE, "anthropic")


# 같은 모델·Provider 도 실제 적용 설정이 다르면 별도 비교 대상이다. 설정까지 같을 때만 막는다
def test_same_model_and_provider_with_different_settings_are_accepted() -> None:
    validate_model_selection(
        [
            ModelSelection(GPT, "openai", {"max_tokens": 512, "temperature": 0.2}),
            ModelSelection(GPT, "openai", {"max_tokens": 512, "temperature": 0.8}),
        ]
    )


@pytest.mark.parametrize(
    "setting", [{"max_tokens": 1024}, {"temperature": 0.5}, {"reasoning_effort": "low"}]
)
def test_each_setting_alone_tells_two_selections_apart(setting: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "max_tokens": 512,
        "temperature": 0.2,
        "reasoning_effort": "high",
    }
    validate_model_selection(
        [
            ModelSelection(GPT, "openai", base),
            ModelSelection(GPT, "openai", {**base, **setting}),
        ]
    )


def test_same_model_provider_and_settings_are_rejected() -> None:
    config = {"max_tokens": 512, "reasoning_effort": "high"}
    second = ModelSelection(GPT, "openai", dict(config))
    with pytest.raises(DuplicateModelSelectionError) as error:
        validate_model_selection([ModelSelection(GPT, "openai", config), second])
    assert error.value.selection == second


def test_setting_order_does_not_matter() -> None:
    with pytest.raises(DuplicateModelSelectionError):
        validate_model_selection(
            [
                ModelSelection(GPT, "openai", {"max_tokens": 512, "temperature": 0.2}),
                ModelSelection(GPT, "openai", {"temperature": 0.2, "max_tokens": 512}),
            ]
        )


def test_the_same_number_written_as_int_or_float_is_the_same_setting() -> None:
    # DB 는 1 과 1.0 을 같은 값으로 보고 같은 해시를 만든다. 서버 검사도 같아야 DB 오류(500)가 나지 않는다
    with pytest.raises(DuplicateModelSelectionError):
        validate_model_selection(
            [
                ModelSelection(GPT, "openai", {"temperature": 1}),
                ModelSelection(GPT, "openai", {"temperature": 1.0}),
            ]
        )


def test_different_models_with_the_same_settings_are_accepted() -> None:
    config = {"max_tokens": 512}
    validate_model_selection(
        [
            ModelSelection(GPT, "openai", config),
            ModelSelection(CLAUDE, "openai", config),
        ]
    )


def test_selection_fields_are_named_after_the_db_columns() -> None:
    # simulation_results 의 model_id, execution_provider 와 이름이 같아야 한다
    selection = ModelSelection(GPT, "openai")
    assert (selection.model_id, selection.execution_provider) == (GPT, "openai")


# 일반 비교 실행에서는 ACTIVE 모델만 고를 수 있다 (기준서 6.5)
@pytest.mark.parametrize(
    ("status", "selectable"),
    [
        (ModelStatus.ACTIVE, True),
        (ModelStatus.TESTING, False),  # 관리자 테스트에서만 선택 가능
        (ModelStatus.INACTIVE, False),
    ],
)
def test_only_active_models_are_selectable(
    status: ModelStatus, selectable: bool
) -> None:
    assert is_model_selectable(status) is selectable


def test_every_model_status_has_a_selectability_decision() -> None:
    # 상태가 새로 생기면 이 규칙도 함께 정하도록 강제한다
    assert {s for s in ModelStatus if is_model_selectable(s)} == {ModelStatus.ACTIVE}

import pytest

from app.services.simulation_validation import (
    MAX_MODEL_COUNT,
    MIN_MODEL_COUNT,
    DuplicateModelSelectionError,
    ModelCountError,
    ModelSelection,
    validate_model_count,
    validate_model_selection,
)

GPT = "openai/gpt-x"
CLAUDE = "anthropic/claude-x"


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


def test_different_models_are_accepted() -> None:
    validate_model_selection([ModelSelection(GPT), ModelSelection(CLAUDE)])


def test_same_model_with_different_providers_is_accepted() -> None:
    # 같은 모델을 Provider 만 바꿔 비교할 수 있다
    validate_model_selection(
        [ModelSelection(GPT, "azure"), ModelSelection(GPT, "openai")]
    )


def test_same_model_with_same_provider_is_rejected() -> None:
    duplicated = ModelSelection(GPT, "openai")
    with pytest.raises(DuplicateModelSelectionError) as error:
        validate_model_selection([ModelSelection(CLAUDE), duplicated, duplicated])
    assert error.value.selection == duplicated


def test_same_model_without_provider_twice_is_rejected() -> None:
    # Provider 를 둘 다 지정하지 않았다면 같은 조건으로 두 번 실행하는 것이다
    with pytest.raises(DuplicateModelSelectionError):
        validate_model_selection([ModelSelection(GPT), ModelSelection(GPT)])


def test_same_model_with_and_without_provider_is_accepted() -> None:
    validate_model_selection([ModelSelection(GPT), ModelSelection(GPT, "openai")])


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
        validate_model_selection([ModelSelection(GPT)])
    five_duplicates = [ModelSelection(GPT, "openai")] * 5
    with pytest.raises(ModelCountError):
        validate_model_selection(five_duplicates)


def test_duplicate_is_found_even_at_the_upper_limit() -> None:
    selections = [
        ModelSelection(GPT, "openai"),
        ModelSelection(CLAUDE),
        ModelSelection(GPT, "azure"),
        ModelSelection(CLAUDE),
    ]
    with pytest.raises(DuplicateModelSelectionError) as error:
        validate_model_selection(selections)
    assert error.value.selection == ModelSelection(CLAUDE)

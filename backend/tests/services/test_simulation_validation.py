import pytest

from app.services.simulation_validation import (
    MAX_MODEL_COUNT,
    MIN_MODEL_COUNT,
    ModelCountError,
    validate_model_count,
)


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

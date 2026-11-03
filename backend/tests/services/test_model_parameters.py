import pytest

from app.schemas.simulation import ReasoningEffort
from app.services.model_parameters import (
    ParameterSupport,
    drop_unsupported,
    narrow_to_provider,
    parameter_support,
    unsupported_parameters,
)

ALL_EFFORTS = tuple(ReasoningEffort)
NO_TEMPERATURE = ParameterSupport(temperature=False, reasoning_efforts=ALL_EFFORTS)
NO_REASONING = ParameterSupport(temperature=True, reasoning_efforts=())
ONLY_LOW_AND_HIGH = ParameterSupport(
    temperature=True,
    reasoning_efforts=(ReasoningEffort.LOW, ReasoningEffort.HIGH),
)


def test_temperature_is_supported_only_when_the_model_lists_it() -> None:
    assert parameter_support(["temperature"]).temperature is True
    assert parameter_support(["max_tokens", "tools"]).temperature is False


def test_reasoning_efforts_are_empty_when_the_model_has_no_reasoning() -> None:
    assert parameter_support(["temperature"]).reasoning_efforts == ()


def test_a_reasoning_model_accepts_every_effort_value() -> None:
    assert parameter_support(["reasoning"]).reasoning_efforts == ALL_EFFORTS


def stored(efforts: list[str] | None, mandatory: bool = False) -> dict[str, object]:
    return {"reasoning": {"mandatory": mandatory, "supported_efforts": efforts}}


# 저장된 값을 읽는 세부 규칙은 stored_reasoning_efforts 의 테스트(test_model_registry)가 맡는다.
# 여기서는 모델 응답(model_common)과 같은 방식으로 합치는지만 본다


def test_a_reasoning_model_accepts_only_the_stored_efforts() -> None:
    support = parameter_support(["reasoning"], stored(["high", "low"]))

    assert support.reasoning_efforts == (ReasoningEffort.LOW, ReasoningEffort.HIGH)


def test_a_reasoning_model_with_an_empty_stored_list_accepts_no_effort() -> None:
    assert parameter_support(["reasoning"], stored([])).reasoning_efforts == ()


def test_a_model_that_must_reason_does_not_accept_none() -> None:
    support = parameter_support(["reasoning"], stored(["none", "low"], mandatory=True))

    assert support.reasoning_efforts == (ReasoningEffort.LOW,)


def test_stored_efforts_do_not_count_without_reasoning() -> None:
    assert parameter_support(["temperature"], stored(["low"])).reasoning_efforts == ()


@pytest.mark.parametrize(
    "metadata",
    [None, {"mock": True}, {"reasoning": {"mandatory": False}}, stored(None)],
)
def test_a_reasoning_model_without_a_stored_list_accepts_every_effort(
    metadata: dict[str, object] | None,
) -> None:
    # 저장 전에 등록된 모델(seed 포함)은 지금처럼 모든 강도를 받는다
    support = parameter_support(["reasoning"], metadata)

    assert support.reasoning_efforts == ALL_EFFORTS


def test_a_model_without_any_listed_parameter_supports_neither() -> None:
    assert parameter_support([]) == ParameterSupport(
        temperature=False, reasoning_efforts=()
    )


def test_max_tokens_never_counts_as_unsupported() -> None:
    nothing = ParameterSupport(temperature=False, reasoning_efforts=())

    assert unsupported_parameters(nothing, {"max_tokens": 512}) == []


def test_an_unsupported_temperature_is_reported_even_when_it_is_zero() -> None:
    # 0 은 유효한 값이라 "값이 없다"로 오해해 지나치면 안 된다
    assert unsupported_parameters(NO_TEMPERATURE, {"temperature": 0.0}) == [
        "temperature"
    ]


def test_an_unsupported_reasoning_model_reports_reasoning_effort() -> None:
    config = {"reasoning_effort": "high"}

    assert unsupported_parameters(NO_REASONING, config) == ["reasoning_effort"]


@pytest.mark.parametrize(
    ("effort", "reported"),
    [("low", []), ("high", []), ("medium", ["reasoning_effort"])],
)
def test_an_effort_outside_the_allowed_values_is_reported(
    effort: str, reported: list[str]
) -> None:
    config = {"reasoning_effort": effort}

    assert unsupported_parameters(ONLY_LOW_AND_HIGH, config) == reported


def test_unsupported_names_follow_the_order_of_the_config() -> None:
    nothing = ParameterSupport(temperature=False, reasoning_efforts=())
    config = {"reasoning_effort": "low", "temperature": 0.3, "max_tokens": 10}

    assert unsupported_parameters(nothing, config) == [
        "reasoning_effort",
        "temperature",
    ]


def test_dropping_removes_only_the_unsupported_settings() -> None:
    config = {"max_tokens": 512, "temperature": 0.3, "reasoning_effort": "medium"}

    kept = drop_unsupported(ONLY_LOW_AND_HIGH, config)

    assert kept == {"max_tokens": 512, "temperature": 0.3}


def test_dropping_does_not_change_the_given_config() -> None:
    config = {"max_tokens": 512, "temperature": 0.3}

    drop_unsupported(NO_TEMPERATURE, config)

    assert config == {"max_tokens": 512, "temperature": 0.3}


# --- 서버 업체별 지원 설정 ---
def test_a_provider_without_temperature_takes_no_temperature() -> None:
    narrowed = narrow_to_provider(ONLY_LOW_AND_HIGH, ["max_tokens", "reasoning"])

    assert narrowed == ParameterSupport(
        temperature=False, reasoning_efforts=ONLY_LOW_AND_HIGH.reasoning_efforts
    )


def test_a_provider_without_reasoning_takes_no_effort() -> None:
    narrowed = narrow_to_provider(ONLY_LOW_AND_HIGH, ["max_tokens", "temperature"])

    assert narrowed == NO_REASONING


def test_a_provider_cannot_add_what_the_model_lacks() -> None:
    assert (
        narrow_to_provider(NO_TEMPERATURE, ["temperature", "reasoning"])
        == NO_TEMPERATURE
    )


@pytest.mark.parametrize("provider_parameters", [None, []])
def test_unknown_provider_settings_keep_the_model_support(
    provider_parameters: list[str] | None,
) -> None:
    # 읽지 못한 업체도 빈 목록으로 온다. 모든 설정을 막지 않고 모델 단위 판단을 그대로 쓴다
    assert narrow_to_provider(ONLY_LOW_AND_HIGH, provider_parameters) == (
        ONLY_LOW_AND_HIGH
    )

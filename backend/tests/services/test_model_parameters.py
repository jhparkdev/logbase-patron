import pytest

from app.schemas.simulation import ReasoningEffort
from app.services.model_parameters import (
    ParameterSupport,
    drop_unsupported,
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


def test_a_reasoning_model_accepts_only_the_efforts_openrouter_listed() -> None:
    metadata = {"reasoning": {"supported_efforts": ["high", "low"]}}

    support = parameter_support(["reasoning"], metadata)

    # 순서는 OpenRouter 가 준 순서가 아니라 ReasoningEffort 의 순서를 따른다
    assert support.reasoning_efforts == (ReasoningEffort.LOW, ReasoningEffort.HIGH)


def test_efforts_we_do_not_know_are_left_out() -> None:
    metadata = {"reasoning": {"supported_efforts": ["low", "turbo", 3]}}

    support = parameter_support(["reasoning"], metadata)

    assert support.reasoning_efforts == (ReasoningEffort.LOW,)


def test_listed_efforts_do_not_count_without_reasoning() -> None:
    metadata = {"reasoning": {"supported_efforts": ["low"]}}

    assert parameter_support(["temperature"], metadata).reasoning_efforts == ()


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"reasoning": None},
        {"reasoning": {}},
        {"reasoning": {"supported_efforts": None}},
        {"reasoning": {"supported_efforts": "low"}},
        {"reasoning": {"supported_efforts": []}},
        {"reasoning": {"supported_efforts": ["turbo"]}},
    ],
)
def test_a_reasoning_model_without_a_usable_effort_list_accepts_every_value(
    metadata: dict[str, object] | None,
) -> None:
    # 목록을 모르는 것과 "지원하지 않는다"는 다르다. 모르면 막지 않고 OpenRouter 에 맡긴다
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

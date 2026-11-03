"""app/mock_data/scenarios.py 테스트: 시뮬레이터 시나리오 템플릿."""

from app.mock_data import scenarios
from app.models import InputType


def test_scenario_codes_are_kept_from_the_previous_seed() -> None:
    codes = [row["scenario_code"] for row in scenarios.scenario_rows()]

    assert codes == [
        "PRODUCT_IMAGE_ANALYSIS",
        "PRODUCT_COPY",
        "DATA_SUMMARY",
        "TEXT_TO_JSON",
        "GENERAL_REASONING",
    ]


def test_data_summary_asks_for_structured_output() -> None:
    row = scenarios.by_code("DATA_SUMMARY")

    assert "JSON Schema" in row.prompt_template
    assert "{{data}}" in row.prompt_template
    assert row.default_json_schema is not None
    assert row.default_json_schema["required"] == ["summary", "key_points"]


def test_data_summary_before_the_change_had_no_schema() -> None:
    assert "JSON Schema" not in scenarios.DATA_SUMMARY_PROMPT_BEFORE_CHANGE
    assert "{{data}}" in scenarios.DATA_SUMMARY_PROMPT_BEFORE_CHANGE


def test_every_template_has_a_placeholder_for_the_input() -> None:
    for scenario in scenarios.SCENARIOS:
        assert "{{" in scenario.prompt_template


def test_only_the_image_scenario_needs_an_image() -> None:
    image = [
        s.scenario_code for s in scenarios.SCENARIOS if s.input_type != InputType.TEXT
    ]

    assert image == ["PRODUCT_IMAGE_ANALYSIS"]

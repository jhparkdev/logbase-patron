"""app/mock_data/sim_answers.py 테스트: 모델 등급별 응답 원문과 JSON 실수."""

from random import Random

import pytest

from app.mock_data import scenarios, sim_answers, sim_content
from app.models import ValidationStatus
from app.services.simulation_json_check import check_json_output

TEXT_TO_JSON_SCHEMA = scenarios.by_code("TEXT_TO_JSON").default_json_schema
SUMMARY_SCHEMA = scenarios.by_code("DATA_SUMMARY").default_json_schema


@pytest.mark.parametrize("product", sim_content.PRODUCTS, ids=lambda p: p.name)
@pytest.mark.parametrize("tier", list(sim_content.Tier))
def test_clean_json_answers_pass_the_scenario_schema(
    product: sim_content.Product, tier: sim_content.Tier
) -> None:
    rng = Random(1)
    converted = sim_answers.text_to_json(product, tier, sim_content.Flaw.NONE, rng)
    summary = sim_answers.structured_summary(product, tier, sim_content.Flaw.NONE)

    for text, schema in ((converted, TEXT_TO_JSON_SCHEMA), (summary, SUMMARY_SCHEMA)):
        check = check_json_output(text, schema)
        assert check.json_parse_status == ValidationStatus.PASSED
        assert check.schema_validation_status == ValidationStatus.PASSED


def test_code_fence_breaks_json_parsing() -> None:
    product = sim_content.PRODUCTS[0]
    text = sim_answers.text_to_json(
        product, sim_content.Tier.LIGHT, sim_content.Flaw.CODE_FENCE, Random(1)
    )

    assert check_json_output(text, TEXT_TO_JSON_SCHEMA).json_parse_status == (
        ValidationStatus.FAILED
    )


def test_missing_field_and_wrong_type_fail_the_schema() -> None:
    product = sim_content.PRODUCTS[0]
    missing = sim_answers.text_to_json(
        product, sim_content.Tier.STANDARD, sim_content.Flaw.MISSING_FIELD, Random(1)
    )
    wrong = sim_answers.text_to_json(
        product, sim_content.Tier.STANDARD, sim_content.Flaw.WRONG_TYPE, Random(1)
    )

    missing_check = check_json_output(missing, TEXT_TO_JSON_SCHEMA)
    assert missing_check.schema_validation_status == ValidationStatus.FAILED
    assert missing_check.missing_required_fields == ["options"]
    wrong_check = check_json_output(wrong, TEXT_TO_JSON_SCHEMA)
    assert wrong_check.json_parse_status == ValidationStatus.PASSED
    assert wrong_check.schema_validation_status == ValidationStatus.FAILED


def test_premium_copy_is_longer_than_light_copy() -> None:
    product = sim_content.PRODUCTS[2]
    premium = sim_answers.product_copy(product, sim_content.Tier.PREMIUM, Random(1))
    light = sim_answers.product_copy(product, sim_content.Tier.LIGHT, Random(1))

    assert len(premium) > len(light)
    assert product.name in premium

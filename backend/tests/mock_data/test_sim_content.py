"""app/mock_data/sim_content.py 테스트: 시뮬레이션 입력 재료."""

from random import Random

from app.mock_data import sim_content
from app.mock_data.model_plans import MODEL_PLANS


def test_every_planned_model_has_a_tier() -> None:
    assert {
        p.openrouter_model_id for p in MODEL_PLANS
    } <= sim_content.MODEL_TIERS.keys()


def test_inputs_mention_the_product() -> None:
    rng = Random(1)
    for product in sim_content.PRODUCTS:
        assert product.name in sim_content.copy_input(product)
        assert product.name in sim_content.unstructured_text(product)
        assert product.name in sim_content.review_data(product)
        assert product.name in sim_content.sales_data(product, rng)

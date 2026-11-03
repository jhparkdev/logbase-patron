"""app/mock_data/model_profiles.py 테스트: 모든 등록 모델에 응답 속도 정보가 있다."""

from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.model_profiles import PROFILES


def test_every_planned_model_has_a_profile() -> None:
    assert {plan.openrouter_model_id for plan in MODEL_PLANS} == PROFILES.keys()


def test_profiles_have_positive_speed_and_a_provider() -> None:
    for profile in PROFILES.values():
        assert profile.first_token_ms > 0
        assert profile.tokens_per_second > 0
        assert profile.providers
        assert 0 <= profile.reasoning_share < 1

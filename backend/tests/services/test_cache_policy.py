"""services/cache_policy.py 테스트. 요청에 cache_control을 붙여야 하는 모델을 가린다."""

import pytest

from app.services.cache_policy import cache_control_for


@pytest.mark.parametrize(
    "model_id",
    [
        "anthropic/claude-sonnet-4.5",
        "anthropic/claude-3.5-haiku",
        "Anthropic/Claude-X",
        "google/gemini-2.5-flash",
        "Google/Gemini-2.5-Pro",
        "qwen/qwen3-max",
    ],
    ids=[
        "Claude",
        "Claude Haiku",
        "대소문자 무시",
        "Gemini",
        "Gemini 대소문자",
        "Qwen",
    ],
)
def test_Claude_Gemini_Qwen_모델은_최상위_cache_control을_붙인다(model_id: str) -> None:
    assert cache_control_for(model_id) == {"type": "ephemeral"}


@pytest.mark.parametrize(
    "model_id",
    [
        "openai/gpt-4o-mini",
        "deepseek/deepseek-chat",
        "x-ai/grok-4",
        "mistralai/mistral-nemo",
        "google/gemma-3-27b-it",
    ],
    ids=["OpenAI 자동", "DeepSeek 자동", "Grok 자동", "Mistral", "Gemma(Gemini 아님)"],
)
def test_자동_캐시이거나_해당하지_않는_모델은_붙이지_않는다(model_id: str) -> None:
    assert cache_control_for(model_id) is None


@pytest.mark.parametrize("model_id", ["", "anthropic", "claude-without-vendor"])
def test_제작사_구분이_없거나_모양이_다르면_붙이지_않는다(model_id: str) -> None:
    assert cache_control_for(model_id) is None


def test_돌려준_값을_바꿔도_다음_결과에_영향이_없다() -> None:
    first = cache_control_for("anthropic/claude-sonnet-4.5")
    assert first is not None
    first["type"] = "changed"

    assert cache_control_for("anthropic/claude-sonnet-4.5") == {"type": "ephemeral"}

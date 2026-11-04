"""요청에 cache_control을 붙여야 하는 모델을 가린다(P-03).

개발자 안내 기준으로 Claude(Anthropic), Gemini, Qwen은 요청에 cache_control을 넣어야 캐시되고,
OpenAI·DeepSeek·Grok 등은 자동으로 캐시되어 붙이지 않는다.
OpenRouter 공식 문서로 확인한 것은 Anthropic이 요청 최상위의 cache_control로 캐시를 켠다는 것까지다.
Gemini는 문서에 자동(암묵) 캐시와 메시지 블록 단위 표시가 함께 나오고, Qwen은 블록 단위 표시를 요구한다고
되어 있어 최상위 값으로 켜지는지는 실제 호출로 확인하지 못했다. 해당하지 않는 모델에는 붙이지 않는다.
"""

# 최상위 cache_control을 붙이는 제작사
TOP_LEVEL_CACHE_VENDORS = ("anthropic", "qwen")
# 같은 제작사(google) 안에서 Gemini 모델만 해당한다(Gemma 등은 제외)
GEMINI_VENDOR = "google"
GEMINI_MODEL_PREFIX = "gemini"
EPHEMERAL_CACHE_CONTROL = {"type": "ephemeral"}


def cache_control_for(openrouter_model_id: str) -> dict[str, str] | None:
    """요청 최상위에 넣을 cache_control. 붙이지 않는 모델이면 None이다."""
    vendor, separator, name = openrouter_model_id.lower().partition("/")
    if not separator:
        return None
    is_gemini = vendor == GEMINI_VENDOR and name.startswith(GEMINI_MODEL_PREFIX)
    if vendor in TOP_LEVEL_CACHE_VENDORS or is_gemini:
        # 호출마다 새 값을 돌려줘, 받은 쪽이 바꿔도 다른 호출에 번지지 않게 한다
        return dict(EPHEMERAL_CACHE_CONTROL)
    return None

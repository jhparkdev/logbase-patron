import pytest

from app.openrouter.request import build_request_body

MESSAGES = [{"role": "user", "content": "안녕"}]
MODEL_ID = "mistralai/mistral-nemo"


def test_기본_요청은_업체_자동_전환을_끈다() -> None:
    body = build_request_body(model_id=MODEL_ID, messages=MESSAGES, max_tokens=100)

    assert body == {
        "model": MODEL_ID,
        "messages": MESSAGES,
        "max_tokens": 100,
        "provider": {"allow_fallbacks": False},
    }


def test_업체를_정하면_provider_order에_담는다() -> None:
    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        provider_order=["DeepInfra"],
    )

    assert body["provider"] == {"allow_fallbacks": False, "order": ["DeepInfra"]}


def test_업체_목록이_비어_있으면_order를_보내지_않는다() -> None:
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, provider_order=[]
    )

    assert "order" not in body["provider"]


def test_업체_자동_전환을_켤_수_있다() -> None:
    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        allow_fallbacks=True,
    )

    assert body["provider"]["allow_fallbacks"] is True


def test_JSON_Schema를_주면_response_format과_require_parameters를_보낸다() -> None:
    schema = {"type": "object", "properties": {"answer": {"type": "integer"}}}

    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        json_schema=schema,
    )

    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "strict": True, "schema": schema},
    }
    # 지원하지 않는 모델이 Schema를 조용히 무시하지 않게 한다 (검증 보고서 API-09)
    assert body["provider"]["require_parameters"] is True


def test_JSON_Schema가_없으면_response_format을_보내지_않는다() -> None:
    body = build_request_body(model_id=MODEL_ID, messages=MESSAGES, max_tokens=100)

    assert "response_format" not in body
    assert "require_parameters" not in body["provider"]


def test_스트리밍을_켜면_stream을_true로_보낸다() -> None:
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, stream=True
    )

    assert body["stream"] is True


def test_temperature를_주면_요청에_담는다() -> None:
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, temperature=0.2
    )

    assert body["temperature"] == 0.2


def test_temperature가_0이어도_요청에_담는다() -> None:
    # 0은 "결정적으로 답하라"는 유효한 값이라 값이 없는 것(None)과 구분한다.
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, temperature=0
    )

    assert body["temperature"] == 0


def test_temperature가_없으면_요청에_담지_않는다() -> None:
    body = build_request_body(model_id=MODEL_ID, messages=MESSAGES, max_tokens=100)

    assert "temperature" not in body


def test_reasoning_effort를_주면_reasoning_객체의_effort로_담는다() -> None:
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, reasoning_effort="high"
    )

    assert body["reasoning"] == {"effort": "high"}


def test_reasoning_effort가_없으면_reasoning을_보내지_않는다() -> None:
    body = build_request_body(model_id=MODEL_ID, messages=MESSAGES, max_tokens=100)

    assert "reasoning" not in body


def test_온도와_추론_설정만으로는_require_parameters를_켜지_않는다() -> None:
    # 지원하지 않는 모델에 보냈을 때 무시할지 실패시킬지는 아직 정해지지 않아 기존 동작을 바꾸지 않는다.
    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        temperature=0.2,
        reasoning_effort="low",
    )

    assert "require_parameters" not in body["provider"]


def test_캐시_설정을_정하지_않으면_본문에_cache_control이_없다() -> None:
    body = build_request_body(model_id=MODEL_ID, messages=MESSAGES, max_tokens=100)

    assert "cache_control" not in body


def test_캐시_설정을_정하면_요청_최상위에_cache_control을_담는다() -> None:
    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        cache_control={"type": "ephemeral"},
    )

    assert body["cache_control"] == {"type": "ephemeral"}


def test_캐시_설정을_넣어도_다른_항목은_그대로이다() -> None:
    plain = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, provider_order=["A"]
    )
    cached = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        provider_order=["A"],
        cache_control={"type": "ephemeral"},
    )

    assert {
        key: value for key, value in cached.items() if key != "cache_control"
    } == plain


def test_캐시_설정은_받은_값을_복사해_담아_밖에서_바꿔도_영향이_없다() -> None:
    control = {"type": "ephemeral"}
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, cache_control=control
    )

    control["type"] = "changed"

    assert body["cache_control"] == {"type": "ephemeral"}


def test_업체_순서와_캐시_설정을_함께_보낼_수_있다() -> None:
    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        provider_order=["Cheap", "Pricey"],
        allow_fallbacks=True,
        cache_control={"type": "ephemeral"},
    )

    assert body["provider"] == {
        "allow_fallbacks": True,
        "order": ["Cheap", "Pricey"],
    }
    assert body["cache_control"] == {"type": "ephemeral"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_models",
            "description": "등록 모델을 조회한다",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


def test_도구를_주면_tools와_자동_선택과_require_parameters를_보낸다() -> None:
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, tools=TOOLS
    )

    assert body["tools"] == TOOLS
    assert body["tool_choice"] == "auto"
    # 도구 호출을 지원하지 않는 업체가 도구를 무시하고 답하지 않게 한다.
    assert body["provider"]["require_parameters"] is True


@pytest.mark.parametrize("tools", [None, []])
def test_도구가_없으면_tools와_tool_choice를_보내지_않는다(
    tools: list[dict[str, object]] | None,
) -> None:
    body = build_request_body(
        model_id=MODEL_ID, messages=MESSAGES, max_tokens=100, tools=tools
    )

    assert "tools" not in body
    assert "tool_choice" not in body
    assert "require_parameters" not in body["provider"]


def test_데이터_수집_거부를_켜면_provider에_deny를_담는다() -> None:
    body = build_request_body(
        model_id=MODEL_ID,
        messages=MESSAGES,
        max_tokens=100,
        deny_data_collection=True,
    )

    assert body["provider"]["data_collection"] == "deny"


def test_데이터_수집_거부는_기본으로_보내지_않는다() -> None:
    body = build_request_body(model_id=MODEL_ID, messages=MESSAGES, max_tokens=100)

    assert "data_collection" not in body["provider"]

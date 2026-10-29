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

from app.openrouter.image_request import build_image_request_body

MODEL_ID = "bytedance-seed/seedream-4.5"
PROMPT = "노을 지는 바다"


def test_기본_요청은_모델과_프롬프트만_담고_업체_자동_전환을_끈다() -> None:
    body = build_image_request_body(model_id=MODEL_ID, prompt=PROMPT)

    assert body == {
        "model": MODEL_ID,
        "prompt": PROMPT,
        "provider": {"allow_fallbacks": False},
    }


def test_업체를_정하면_provider_order에_담는다() -> None:
    body = build_image_request_body(
        model_id=MODEL_ID, prompt=PROMPT, provider_order=["bytedance"]
    )

    assert body["provider"] == {"allow_fallbacks": False, "order": ["bytedance"]}


def test_업체_목록이_비어_있으면_order를_보내지_않는다() -> None:
    body = build_image_request_body(model_id=MODEL_ID, prompt=PROMPT, provider_order=[])

    assert "order" not in body["provider"]


def test_업체_자동_전환을_켤_수_있다() -> None:
    body = build_image_request_body(
        model_id=MODEL_ID, prompt=PROMPT, allow_fallbacks=True
    )

    assert body["provider"]["allow_fallbacks"] is True


def test_참고_이미지는_순서대로_image_url_조각으로_담는다() -> None:
    urls = ["data:image/png;base64,AAAA", "data:image/jpeg;base64,BBBB"]

    body = build_image_request_body(
        model_id=MODEL_ID, prompt=PROMPT, input_image_urls=urls
    )

    assert body["input_references"] == [
        {"type": "image_url", "image_url": {"url": urls[0]}},
        {"type": "image_url", "image_url": {"url": urls[1]}},
    ]


def test_참고_이미지가_비어_있으면_input_references를_보내지_않는다() -> None:
    body = build_image_request_body(
        model_id=MODEL_ID, prompt=PROMPT, input_image_urls=[]
    )

    assert "input_references" not in body


def test_생성_설정은_값을_주었을_때만_담는다() -> None:
    body = build_image_request_body(
        model_id=MODEL_ID,
        prompt=PROMPT,
        n=2,
        resolution="2K",
        aspect_ratio="16:9",
        quality="high",
    )

    assert body["n"] == 2
    assert body["resolution"] == "2K"
    assert body["aspect_ratio"] == "16:9"
    assert body["quality"] == "high"


def test_생성_설정을_주지_않으면_요청에_없다() -> None:
    body = build_image_request_body(model_id=MODEL_ID, prompt=PROMPT)

    for key in ("n", "resolution", "aspect_ratio", "quality", "stream"):
        assert key not in body

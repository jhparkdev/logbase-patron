"""OpenRouter 이미지 생성(/images)에 보낼 요청 본문을 만든다."""

from typing import Any

IMAGE_REFERENCE_TYPE = "image_url"


def build_image_request_body(
    *,
    model_id: str,
    prompt: str,
    input_image_urls: list[str] | None = None,
    n: int | None = None,
    resolution: str | None = None,
    aspect_ratio: str | None = None,
    quality: str | None = None,
    provider_order: list[str] | None = None,
    allow_fallbacks: bool = False,
) -> dict[str, Any]:
    # 업체 자동 전환은 기본으로 끈다. 비교 조건이 바뀌지 않게 하기 위해서다.
    provider: dict[str, Any] = {"allow_fallbacks": allow_fallbacks}
    if provider_order:
        provider["order"] = provider_order

    body: dict[str, Any] = {"model": model_id, "prompt": prompt, "provider": provider}

    # 참고 이미지는 data URL(또는 HTTP(S) URL)이다. 순서를 그대로 보낸다.
    if input_image_urls:
        body["input_references"] = [
            {"type": IMAGE_REFERENCE_TYPE, "image_url": {"url": url}}
            for url in input_image_urls
        ]

    # 값의 범위는 호출하는 쪽이 검증한다. 준 값만 보낸다.
    options = {
        "n": n,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
    }
    body.update({key: value for key, value in options.items() if value is not None})
    return body

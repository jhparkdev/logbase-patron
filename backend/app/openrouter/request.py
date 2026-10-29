"""OpenRouter에 보낼 요청 본문을 만든다."""

from typing import Any

JSON_SCHEMA_NAME = "response"


def build_request_body(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    json_schema: dict[str, Any] | None = None,
    provider_order: list[str] | None = None,
    allow_fallbacks: bool = False,
    stream: bool = False,
) -> dict[str, Any]:
    # 업체 자동 전환은 기본으로 끈다. 비교 조건이 바뀌지 않게 하기 위해서다.
    provider: dict[str, Any] = {"allow_fallbacks": allow_fallbacks}
    if provider_order:
        provider["order"] = provider_order

    body: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "provider": provider,
    }

    if stream:
        body["stream"] = True

    if json_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": JSON_SCHEMA_NAME,
                "strict": True,
                "schema": json_schema,
            },
        }
        # Schema를 지원하지 않는 모델이 조용히 무시하지 않고 404로 실패하게 한다.
        provider["require_parameters"] = True

    return body

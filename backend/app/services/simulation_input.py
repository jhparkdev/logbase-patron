import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.schemas.simulation import MAX_TOKENS_LIMIT
from app.services.simulation_ports import ImageRef

# 팀이 정한 임시 수치(결정됨)와 하트비트 주기
SIMULATION_TIMEOUT_SECONDS = 180
HEARTBEAT_INTERVAL_SECONDS = 30

# 요청과 시나리오 모두 정하지 않았을 때의 최대 토큰. 사용자 입력 상한과 같게 정했다.
# 추론 모델은 생각한 토큰도 이 한도에 들어가서, 낮으면 답이 비고 비용만 나간다
DEFAULT_MAX_TOKENS = MAX_TOKENS_LIMIT

# call_model 이 실제로 보내는 실행 설정. 보내지 못하는 값을 기록하면 기록과 호출이 달라지므로
# 이 목록의 값만 남긴다. call_model 에 새 인자가 생기면 목록에 더한다
SENT_EXECUTION_SETTINGS = ("max_tokens", "temperature", "reasoning_effort")

_PLACEHOLDER = re.compile(r"\{\{[^{}]+\}\}")

# DB 에 남는 메시지에서 이미지를 가리키는 표시. 이미지 내용 대신 asset_id 만 넣는다
IMAGE_REF_PREFIX = "asset:"


class MissingImageDataError(LookupError):
    """메시지가 가리키는 이미지의 내용을 구하지 못했다. 참조 표시 그대로 모델에 보내지 않으려고 멈춘다."""


class InputRequiredError(ValueError):
    """프롬프트에 {{...}} 자리가 있는데 채울 입력 데이터가 비어 있다."""

    def __init__(self) -> None:
        super().__init__("템플릿 자리를 채울 입력 데이터가 필요하다")


def _has_input(input_text: str | None) -> bool:
    return bool(input_text and input_text.strip())


def validate_input_present(prompt_text: str, input_text: str | None) -> None:
    """템플릿 자리가 있는데 입력이 비어 있으면 거절한다. 요청 접수 때 호출한다.

    자리를 채우지 못한 글("{{product_info}}")이 모델에 가면 비교가 의미 없어지고 비용만 나간다.
    """
    if _PLACEHOLDER.search(prompt_text) and not _has_input(input_text):
        raise InputRequiredError


def build_prompt_text(prompt_text: str, input_text: str | None) -> str:
    """모델에 보낼 글을 만든다. 모든 모델에 같은 글이 간다.

    템플릿의 {{...}} 자리에 입력을 한 번에 끼운다. 자리가 없으면 입력을 뒤에 붙이고,
    입력이 없으면 사용자가 쓴 프롬프트를 바꾸지 않는다(자리가 있는 경우는 접수 때 거절한다).
    """
    if not _has_input(input_text):
        return prompt_text
    if _PLACEHOLDER.search(prompt_text):
        # 함수로 치환해야 입력 안의 역슬래시가 해석되지 않고, 입력 안의 {{...}} 도 다시 바뀌지 않는다
        return _PLACEHOLDER.sub(lambda _: input_text, prompt_text)
    return f"{prompt_text}\n\n{input_text}"


def build_messages(text: str, images: Sequence[ImageRef] = ()) -> list[dict[str, Any]]:
    """call_model 이 받는 형태: {role, content} 딕셔너리의 목록. 사용자 메시지 하나다.

    이미지가 있으면 content 가 글과 이미지 조각의 목록이 된다(OpenRouter 의 image_url 형식).
    이 값이 DB 에 저장되므로 이미지는 내용이 아니라 참조(asset:<asset_id>)로만 넣는다.
    모델에 보낼 때는 inline_images 로 내용으로 바꾼다.
    """
    if not images:
        return [{"role": "user", "content": text}]
    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
    parts.extend(
        {
            "type": "image_url",
            "image_url": {"url": f"{IMAGE_REF_PREFIX}{image.asset_id}"},
        }
        for image in images
    )
    return [{"role": "user", "content": parts}]


def inline_images(
    messages: Sequence[Mapping[str, Any]], data_urls: Mapping[str, str]
) -> list[dict[str, Any]]:
    """저장용 메시지의 이미지 참조를 내용(data URL)으로 바꾼 복사본을 만든다. 원본은 바꾸지 않는다.

    data_urls 는 asset_id(문자열) → data URL 이다. 내용이 없는 참조가 있으면 그대로 보내지 않고 멈춘다.
    """
    return [
        {**message, "content": _inline_content(message["content"], data_urls)}
        for message in messages
    ]


def _inline_content(content: Any, data_urls: Mapping[str, str]) -> Any:
    if not isinstance(content, list):
        return content
    return [_inline_part(part, data_urls) for part in content]


def _inline_part(part: Mapping[str, Any], data_urls: Mapping[str, str]) -> Any:
    if part.get("type") != "image_url":
        return part
    url = part["image_url"]["url"]
    if not url.startswith(IMAGE_REF_PREFIX):
        return part
    asset_id = url.removeprefix(IMAGE_REF_PREFIX)
    if asset_id not in data_urls:
        raise MissingImageDataError(asset_id)
    return {**part, "image_url": {**part["image_url"], "url": data_urls[asset_id]}}


def compute_input_hash(prompt_text: str, input_text: str | None) -> str:
    """실행의 입력 해시. seed 와 같은 식(sha256(프롬프트 + 입력 텍스트))이다.

    합치기 전의 원본 두 조각으로 계산한다. Schema 는 넣지 않는다.
    """
    return hashlib.sha256(f"{prompt_text}{input_text or ''}".encode()).hexdigest()


def resolve_execution_config(
    requested: Mapping[str, Any], scenario_default: Mapping[str, Any] | None
) -> dict[str, Any]:
    """실제로 보낼 실행 설정. 기록(simulation_runs·ai_requests)에도 이 값이 그대로 남는다.

    요청에 없는 설정은 시나리오 기본값으로 채우고, 요청에 있는 값이 항목별로 우선한다.
    최대 토큰은 call_model 이 반드시 받으므로 아무도 정하지 않으면 기본값을 쓴다.
    temperature 와 reasoning_effort 는 아무도 정하지 않으면 담지 않고 모델 기본값에 맡긴다.
    """
    merged = {"max_tokens": DEFAULT_MAX_TOKENS, **(scenario_default or {}), **requested}
    return {key: merged[key] for key in SENT_EXECUTION_SETTINGS if key in merged}


def resolve_slot_config(
    run_config: Mapping[str, Any], slot_override: Mapping[str, Any]
) -> dict[str, Any]:
    """모델 한 칸에 실제로 적용할 설정. 칸에서 정한 항목이 실행 공통 설정보다 항목별로 우선한다.

    기록(ai_requests)에도 이 값이 그대로 남고, 같은 모델·Provider 의 중복 판정도 이 값으로 한다.
    """
    merged = {**run_config, **slot_override}
    return {key: merged[key] for key in SENT_EXECUTION_SETTINGS if key in merged}


def resolve_json_schema(
    requested: dict[str, Any] | None, scenario_default: dict[str, Any] | None
) -> dict[str, Any] | None:
    """요청에 Schema 가 없으면 시나리오 기본 Schema 를 쓴다."""
    return requested if requested is not None else scenario_default


def build_run_routing_policy(
    *, allow_fallbacks: bool, has_json_schema: bool
) -> dict[str, Any]:
    """simulation_runs.routing_policy 에 저장할 값.

    require_parameters 는 call_model 이 Schema 가 있을 때만 켠다. 실제로 보낸 값과 같게 기록한다.
    """
    return {"allow_fallbacks": allow_fallbacks, "require_parameters": has_json_schema}


def build_request_routing_policy(
    run_policy: Mapping[str, Any], execution_provider: str
) -> dict[str, Any]:
    """ai_requests.routing_policy 에 저장할 값. 이 칸에서 고정한 업체가 order 에 들어간다."""
    return {**run_policy, "order": [execution_provider]}

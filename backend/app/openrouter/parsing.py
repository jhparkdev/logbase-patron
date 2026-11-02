"""OpenRouter chat/completions 응답을 CallResult로 바꾼다.

외부에서 온 값이라 모양을 믿지 않고 하나씩 확인한다.
"""

import json
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.json_access import get_dict, get_int, get_number, get_str
from app.openrouter.result import (
    CallResult,
    CallStatus,
    CostSource,
    CostStatus,
    elapsed_ms,
)


def loads_decimal(text: str) -> Any:
    """JSON 문자열을 읽되, 소수는 float이 아니라 Decimal로 읽는다."""
    return json.loads(text, parse_float=Decimal)


GENERATION_ID_HEADER = "X-Generation-Id"
# 호출 조회(/generation)가 받는 ID 형식. 공식 문서의 규칙이다.
GENERATION_ID_PATTERN = re.compile(r"gen-[0-9A-Za-z-]+")
MAX_GENERATION_ID_LENGTH = 128


def clean_generation_id(value: str | None) -> str | None:
    """호출 ID로 쓸 수 있는 값만 돌려준다. 없거나 형식이 틀리면 None."""
    if value is None or len(value) > MAX_GENERATION_ID_LENGTH:
        return None
    if not GENERATION_ID_PATTERN.fullmatch(value):
        return None
    return value


def generation_id_from_headers(headers: Mapping[str, str]) -> str | None:
    """응답 헤더에서 호출 ID를 꺼낸다. 없거나 형식이 틀리면 None."""
    return clean_generation_id(headers.get(GENERATION_ID_HEADER))


def _get_first_choice(body: dict[str, Any]) -> dict[str, Any]:
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def get_cost(usage: dict[str, Any]) -> Decimal | None:
    """usage.cost를 Decimal로 돌려준다. 없거나 믿을 수 없으면 None."""
    cost = get_number(usage, "cost")
    if cost is None or cost < 0:
        return None
    return cost


def build_result_from_chat_body(
    body: dict[str, Any],
    *,
    requested_model: str,
    started_at: datetime,
    finished_at: datetime,
    http_status: int,
    generation_id_header: str | None = None,
) -> CallResult:
    """HTTP 200으로 온 응답 본문을 CallResult로 바꾼다.

    호출 ID는 본문의 id를 우선하고, 없으면 헤더에서 읽은 값을 쓴다.
    """
    choice = _get_first_choice(body)
    message = get_dict(choice, "message")
    usage = get_dict(body, "usage")
    prompt_details = get_dict(usage, "prompt_tokens_details")
    completion_details = get_dict(usage, "completion_tokens_details")

    content = get_str(message, "content")
    actual_model = get_str(body, "model")
    prompt_tokens = get_int(usage, "prompt_tokens")
    completion_tokens = get_int(usage, "completion_tokens")

    common_fields: dict[str, Any] = {
        "http_status": http_status,
        "content": content,
        "finish_reason": get_str(choice, "finish_reason"),
        "requested_model": requested_model,
        "actual_model": actual_model,
        "provider": get_str(body, "provider"),
        "generation_id": get_str(body, "id") or generation_id_header,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": get_int(usage, "total_tokens"),
        "cached_tokens": get_int(prompt_details, "cached_tokens"),
        "cache_write_tokens": get_int(prompt_details, "cache_write_tokens"),
        "reasoning_tokens": get_int(completion_details, "reasoning_tokens"),
        "raw_response": body,
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": elapsed_ms(started_at, finished_at),
    }

    # 본문, 실제 모델, 토큰 수 중 하나라도 없으면 성공으로 보지 않는다.
    has_content = content is not None and content.strip() != ""
    is_valid = (
        has_content
        and bool(actual_model)
        and prompt_tokens is not None
        and completion_tokens is not None
    )
    if not is_valid:
        return CallResult(
            **common_fields,
            status=CallStatus.FAILED,
            error_type=ErrorType.INVALID_RESPONSE,
            error_message=USER_MESSAGES[ErrorType.INVALID_RESPONSE],
            cost_status=CostStatus.UNKNOWN,
        )

    cost = get_cost(usage)
    if cost is None:
        return CallResult(
            **common_fields,
            status=CallStatus.SUCCESS,
            cost_status=CostStatus.UNKNOWN,
        )

    return CallResult(
        **common_fields,
        status=CallStatus.SUCCESS,
        cost_usd=cost,
        cost_status=CostStatus.CONFIRMED,
        cost_source=CostSource.API_RESPONSE,
    )

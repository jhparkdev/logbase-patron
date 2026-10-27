"""OpenRouter chat/completions 응답을 CallResult로 바꾼다.

외부에서 온 값이라 모양을 믿지 않고 하나씩 확인한다.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.openrouter.errors import USER_MESSAGES, ErrorType
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


def _get_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _get_str(parent: dict[str, Any], key: str) -> str | None:
    value = parent.get(key)
    if isinstance(value, str):
        return value
    return None


def _get_int(parent: dict[str, Any], key: str) -> int | None:
    value = parent.get(key)
    # True/False는 파이썬에서 int이므로 따로 걸러낸다.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _get_first_choice(body: dict[str, Any]) -> dict[str, Any]:
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def _get_cost(usage: dict[str, Any]) -> Decimal | None:
    """usage.cost를 Decimal로 돌려준다. 없거나 믿을 수 없으면 None."""
    cost = usage.get("cost")
    if isinstance(cost, bool) or not isinstance(cost, (int, float, Decimal)):
        return None
    # float이 와도 문자열을 거쳐 Decimal로 바꾼다. float로 계산하지는 않는다.
    if isinstance(cost, float):
        cost = Decimal(str(cost))
    value = Decimal(cost)
    if value < 0:
        return None
    return value


def build_result_from_chat_body(
    body: dict[str, Any],
    *,
    requested_model: str,
    started_at: datetime,
    finished_at: datetime,
    http_status: int,
) -> CallResult:
    """HTTP 200으로 온 응답 본문을 CallResult로 바꾼다."""
    choice = _get_first_choice(body)
    message = _get_dict(choice, "message")
    usage = _get_dict(body, "usage")
    prompt_details = _get_dict(usage, "prompt_tokens_details")
    completion_details = _get_dict(usage, "completion_tokens_details")

    content = _get_str(message, "content")
    actual_model = _get_str(body, "model")
    prompt_tokens = _get_int(usage, "prompt_tokens")
    completion_tokens = _get_int(usage, "completion_tokens")

    common_fields: dict[str, Any] = {
        "http_status": http_status,
        "content": content,
        "finish_reason": _get_str(choice, "finish_reason"),
        "requested_model": requested_model,
        "actual_model": actual_model,
        "provider": _get_str(body, "provider"),
        "generation_id": _get_str(body, "id"),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": _get_int(usage, "total_tokens"),
        "cached_tokens": _get_int(prompt_details, "cached_tokens"),
        "cache_write_tokens": _get_int(prompt_details, "cache_write_tokens"),
        "reasoning_tokens": _get_int(completion_details, "reasoning_tokens"),
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

    cost = _get_cost(usage)
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

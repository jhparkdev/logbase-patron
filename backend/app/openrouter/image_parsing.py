"""OpenRouter 이미지 생성(/images) 응답을 ImageCallResult로 바꾼다.

외부에서 온 값이라 모양을 믿지 않고 하나씩 확인한다.
"""

import base64
from datetime import datetime
from typing import Any

import httpx

from app.openrouter.errors import (
    USER_MESSAGES,
    ErrorType,
    classify_http_error,
    get_failed_routing_step,
)
from app.openrouter.failures import CANCELLED_MESSAGE
from app.openrouter.image_result import GeneratedImage, ImageCallResult
from app.openrouter.json_access import get_dict, get_int, get_list, get_str
from app.openrouter.parsing import get_cost
from app.openrouter.result import CallStatus, CostSource, CostStatus, elapsed_ms

IMAGE_DATA_KEY = "b64_json"


def _decode_images(data: list[Any]) -> tuple[GeneratedImage, ...] | None:
    """data 목록을 이미지로 푼다. 하나라도 비었거나 base64가 아니면 None."""
    images: list[GeneratedImage] = []
    for item in data:
        encoded = get_str(item, IMAGE_DATA_KEY) if isinstance(item, dict) else None
        if not encoded:
            return None
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except ValueError:
            # base64가 아닌 문자(binascii.Error)와 ASCII가 아닌 문자(ValueError)를 함께 잡는다.
            return None
        images.append(
            GeneratedImage(data=decoded, media_type=get_str(item, "media_type"))
        )
    return tuple(images)


def _without_image_data(body: dict[str, Any]) -> dict[str, Any]:
    """응답 원문에서 이미지 내용만 뺀다. 장당 수 MB라 DB에 그대로 남기지 않는다."""
    stripped = dict(body)
    data = body.get("data")
    if isinstance(data, list):
        stripped["data"] = [
            {key: value for key, value in item.items() if key != IMAGE_DATA_KEY}
            if isinstance(item, dict)
            else item
            for item in data
        ]
    return stripped


def _cost_fields(usage: dict[str, Any]) -> dict[str, Any]:
    cost = get_cost(usage)
    if cost is None:
        return {"cost_status": CostStatus.UNKNOWN}
    return {
        "cost_usd": cost,
        "cost_status": CostStatus.CONFIRMED,
        "cost_source": CostSource.API_RESPONSE,
    }


def _result_from_success_body(
    body: dict[str, Any], common: dict[str, Any]
) -> ImageCallResult:
    usage = get_dict(body, "usage")
    completion_details = get_dict(usage, "completion_tokens_details")
    fields: dict[str, Any] = {
        **common,
        "prompt_tokens": get_int(usage, "prompt_tokens"),
        "completion_tokens": get_int(usage, "completion_tokens"),
        "total_tokens": get_int(usage, "total_tokens"),
        "image_tokens": get_int(completion_details, "image_tokens"),
        "raw_response": _without_image_data(body),
        # 이미지 응답에는 호출 ID가 없어 나중에 비용을 대조할 수 없다.
        # 그래서 응답이 깨졌어도 받은 비용은 버리지 않는다.
        **_cost_fields(usage),
    }

    # 채팅 응답과 달리 실제 모델·업체 필드가 없고 usage도 선택이다. 이미지가 있어야만 성공이다.
    data = get_list(body, "data")
    images = _decode_images(data) if data else None
    if images is None:
        return ImageCallResult(
            **fields,
            status=CallStatus.FAILED,
            error_type=ErrorType.INVALID_RESPONSE,
            error_message=USER_MESSAGES[ErrorType.INVALID_RESPONSE],
        )
    return ImageCallResult(**fields, status=CallStatus.SUCCESS, images=images)


def build_image_result(
    *,
    status_code: int,
    body: Any,
    requested_model: str,
    started_at: datetime,
    finished_at: datetime,
    generation_id: str | None = None,
) -> ImageCallResult:
    """받은 응답을 ImageCallResult로 바꾼다. body는 JSON으로 읽은 값이고, 못 읽었으면 None이다.

    generation_id는 응답 헤더에서 읽은 호출 ID다. 공식 문서에는 없어서 있을 때만 쓴다.
    """
    common: dict[str, Any] = {
        "http_status": status_code,
        "requested_model": requested_model,
        "generation_id": generation_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "latency_ms": elapsed_ms(started_at, finished_at),
    }

    if httpx.codes.is_success(status_code):
        if isinstance(body, dict):
            return _result_from_success_body(body, common)
        return ImageCallResult(
            **common,
            status=CallStatus.FAILED,
            error_type=ErrorType.INVALID_RESPONSE,
            error_message=USER_MESSAGES[ErrorType.INVALID_RESPONSE],
        )

    error_body = body if isinstance(body, dict) else None
    error_type = classify_http_error(status_code, error_body)
    return ImageCallResult(
        **common,
        status=CallStatus.FAILED,
        error_type=error_type,
        error_message=USER_MESSAGES[error_type],
        failed_routing_step=get_failed_routing_step(error_body),
        raw_response=error_body,
    )


def build_image_failure_result(
    *,
    status: CallStatus,
    error_type: ErrorType,
    requested_model: str,
    started_at: datetime,
    finished_at: datetime,
) -> ImageCallResult:
    """응답을 받지 못한 호출(시간 초과, 연결 실패)의 결과다."""
    return ImageCallResult(
        status=status,
        error_type=error_type,
        error_message=USER_MESSAGES[error_type],
        requested_model=requested_model,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=elapsed_ms(started_at, finished_at),
    )


def build_image_cancelled_result(
    *, requested_model: str, started_at: datetime, finished_at: datetime
) -> ImageCallResult:
    # 문서상 끝나지 않은 생성은 과금되지 않지만, 끊는 순간 업체 쪽에서 끝났을 수 있다.
    # 그래서 비용은 0이 아니라 미확인으로 둔다.
    return ImageCallResult(
        status=CallStatus.CANCELLED,
        error_message=CANCELLED_MESSAGE,
        requested_model=requested_model,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=elapsed_ms(started_at, finished_at),
    )

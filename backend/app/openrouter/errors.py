"""OpenRouter 호출 오류를 회사 문서가 정한 오류 유형 8종으로 분류한다.

HTTP 상태 코드와 오류 유형의 매핑은 이 파일 한 곳에만 둔다.
"""

from enum import StrEnum
from http import HTTPStatus
from typing import Any


class ErrorType(StrEnum):
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# 404 본문의 failed_routing_step 값별 오류 유형.
# 세 값 모두 검증 보고서(API-08, 09, 10)에서 실제 응답으로 확인했다.
ROUTING_STEP_ERROR_TYPES = {
    "Filter by Fallback": ErrorType.PROVIDER_ERROR,
    "Filter by Image Support": ErrorType.UNSUPPORTED_INPUT,
    "Filter by Parameters": ErrorType.UNSUPPORTED_INPUT,
}

# 화면에 보여 줄 문구. Key, Prompt, 내부 예외 문구는 넣지 않는다.
USER_MESSAGES = {
    ErrorType.AUTH_ERROR: "OpenRouter 인증에 실패했습니다.",
    ErrorType.RATE_LIMIT: "호출이 너무 많아 잠시 제한되었습니다.",
    ErrorType.TIMEOUT_ERROR: "응답 시간이 초과되었습니다.",
    ErrorType.PROVIDER_ERROR: "모델을 제공하는 업체에서 오류가 발생했습니다.",
    ErrorType.NETWORK_ERROR: "OpenRouter에 연결하지 못했습니다.",
    ErrorType.INVALID_RESPONSE: "OpenRouter 응답에 필요한 정보가 없습니다.",
    ErrorType.UNSUPPORTED_INPUT: "선택한 모델이 이 입력이나 형식을 지원하지 않습니다.",
    ErrorType.UNKNOWN_ERROR: "알 수 없는 오류가 발생했습니다.",
}

SERVER_ERROR_STATUS_CODES = range(500, 600)


def get_failed_routing_step(body: dict[str, Any] | None) -> str | None:
    """오류 응답 본문에서 라우팅이 실패한 단계 이름을 꺼낸다. 없으면 None."""
    if not isinstance(body, dict):
        return None

    error = body.get("error")
    if not isinstance(error, dict):
        return None

    metadata = error.get("metadata")
    if not isinstance(metadata, dict):
        return None

    step = metadata.get("failed_routing_step")
    if not isinstance(step, str):
        return None

    return step


def classify_http_error(status_code: int, body: dict[str, Any] | None) -> ErrorType:
    """HTTP 오류 응답을 오류 유형 8종 중 하나로 분류한다."""
    if status_code == HTTPStatus.UNAUTHORIZED:
        return ErrorType.AUTH_ERROR

    if status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return ErrorType.RATE_LIMIT

    if status_code == HTTPStatus.NOT_FOUND:
        step = get_failed_routing_step(body)
        if step is None:
            return ErrorType.UNKNOWN_ERROR
        return ROUTING_STEP_ERROR_TYPES.get(step, ErrorType.UNKNOWN_ERROR)

    if status_code in SERVER_ERROR_STATUS_CODES:
        return ErrorType.PROVIDER_ERROR

    # 400(없는 모델 ID 등)은 회사 확인 대기(U-03)라 임시로 여기에 온다.
    # 402·403도 실제 응답을 확인하기 전까지 UNKNOWN_ERROR로 둔다.
    # 401, 429, 5xx 매핑도 아직 실제 응답으로 확인하지 않았다.
    return ErrorType.UNKNOWN_ERROR

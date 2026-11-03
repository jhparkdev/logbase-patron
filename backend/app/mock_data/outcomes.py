"""호출 결과(성공·실패 유형)와 실패 유형별 응답 모양.

HTTP 상태와 오류 유형의 짝은 app/openrouter/errors.py의 분류 규칙과 맞춘다.
"""

from dataclasses import dataclass
from random import Random

from pydantic import JsonValue

from app.models import ErrorType, RequestStatus

HTTP_OK = 200


@dataclass(frozen=True)
class Outcome:
    status: RequestStatus
    error_type: ErrorType | None = None
    http_status: int | None = HTTP_OK
    error_message: str | None = None
    error_detail: dict[str, JsonValue] | None = None
    # 실패 응답까지 걸린 시간 범위. 성공은 모델 속도로 계산한다
    latency_ms: tuple[int, int] = (0, 0)
    retryable: bool = False  # 고객 서비스가 한 번 더 시도하는 일시적 오류


SUCCESS = Outcome(RequestStatus.SUCCESS)
# 클라이언트 timeout. 응답 없이 끊긴다.
TIMEOUT_MS = 60_000

FAILURES = {
    ErrorType.RATE_LIMIT: Outcome(
        RequestStatus.FAILED, ErrorType.RATE_LIMIT, 429, "Rate limit exceeded",
        latency_ms=(150, 600), retryable=True,
    ),
    ErrorType.PROVIDER_ERROR: Outcome(
        RequestStatus.FAILED, ErrorType.PROVIDER_ERROR, 502, "Provider returned error",
        latency_ms=(800, 4000), retryable=True,
    ),
    ErrorType.TIMEOUT_ERROR: Outcome(
        RequestStatus.TIMEOUT, ErrorType.TIMEOUT_ERROR, None, "Client timeout",
        latency_ms=(TIMEOUT_MS, TIMEOUT_MS), retryable=True,
    ),
    ErrorType.NETWORK_ERROR: Outcome(
        RequestStatus.FAILED, ErrorType.NETWORK_ERROR, None, "Connection reset by peer",
        latency_ms=(100, 3000), retryable=True,
    ),
    ErrorType.INVALID_RESPONSE: Outcome(
        RequestStatus.FAILED, ErrorType.INVALID_RESPONSE, HTTP_OK,
        "Response has no choices", latency_ms=(2000, 8000),
    ),
    ErrorType.UNSUPPORTED_INPUT: Outcome(
        RequestStatus.FAILED, ErrorType.UNSUPPORTED_INPUT, 404,
        "No endpoints found that support the requested parameters",
        {"failed_routing_step": "Filter by Parameters"}, latency_ms=(100, 300),
    ),
    ErrorType.AUTH_ERROR: Outcome(
        RequestStatus.FAILED, ErrorType.AUTH_ERROR, 401, "User not found.",
        latency_ms=(80, 200),
    ),
    ErrorType.UNKNOWN_ERROR: Outcome(
        RequestStatus.FAILED, ErrorType.UNKNOWN_ERROR, 404, "Not Found",
        latency_ms=(200, 800),
    ),
}  # fmt: skip

# 실패 유형별 상대 빈도. 일시적인 제한·업체 오류가 대부분이다.
FAILURE_WEIGHTS = {
    ErrorType.RATE_LIMIT: 30,
    ErrorType.PROVIDER_ERROR: 28,
    ErrorType.TIMEOUT_ERROR: 15,
    ErrorType.NETWORK_ERROR: 6,
    ErrorType.INVALID_RESPONSE: 6,
    ErrorType.UNSUPPORTED_INPUT: 7,
    ErrorType.AUTH_ERROR: 3,
    ErrorType.UNKNOWN_ERROR: 5,
}


def sample_outcome(failure_rate: float, rng: Random) -> Outcome:
    if rng.random() >= failure_rate:
        return SUCCESS
    error_type = rng.choices(
        list(FAILURE_WEIGHTS), weights=list(FAILURE_WEIGHTS.values())
    )[0]
    return FAILURES[error_type]

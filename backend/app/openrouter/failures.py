"""실패하거나 취소된 호출의 CallResult를 만든다."""

from datetime import datetime
from typing import Any

from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.result import CallResult, CallStatus, CostStatus, elapsed_ms

CANCELLED_MESSAGE = "호출이 취소되었습니다."


def build_failure_result(
    *,
    status: CallStatus,
    error_type: ErrorType,
    requested_model: str,
    started_at: datetime,
    finished_at: datetime,
    http_status: int | None = None,
    failed_routing_step: str | None = None,
    raw_response: dict[str, Any] | None = None,
    generation_id: str | None = None,
) -> CallResult:
    return CallResult(
        status=status,
        error_type=error_type,
        error_message=USER_MESSAGES[error_type],
        http_status=http_status,
        failed_routing_step=failed_routing_step,
        requested_model=requested_model,
        cost_status=CostStatus.UNKNOWN,
        raw_response=raw_response,
        generation_id=generation_id,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=elapsed_ms(started_at, finished_at),
    )


def build_cancelled_result(
    *,
    requested_model: str,
    started_at: datetime,
    finished_at: datetime,
    generation_id: str | None = None,
) -> CallResult:
    # 취소는 오류가 아니라 실행 상태다. 취소해도 이미 처리된 토큰만큼 과금될 수 있어
    # 비용은 0이 아니라 미확인으로 둔다. 호출 ID를 알면 남겨서 나중에 비용을 대조한다.
    return CallResult(
        status=CallStatus.CANCELLED,
        error_message=CANCELLED_MESSAGE,
        requested_model=requested_model,
        cost_status=CostStatus.UNKNOWN,
        generation_id=generation_id,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=elapsed_ms(started_at, finished_at),
    )

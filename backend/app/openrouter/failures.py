"""호출이 실패했을 때의 CallResult를 만든다."""

from datetime import datetime
from typing import Any

from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.result import CallResult, CallStatus, CostStatus, elapsed_ms


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
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=elapsed_ms(started_at, finished_at),
    )

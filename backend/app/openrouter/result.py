"""call_model이 돌려주는 결과 모양.

call_model은 실패해도 예외를 던지지 않고 이 결과로 실패를 알린다.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.openrouter.errors import ErrorType

TRUNCATED_FINISH_REASON = "length"
MILLISECONDS_PER_SECOND = 1000


def elapsed_ms(started_at: datetime, finished_at: datetime) -> int:
    """두 시각 사이의 시간을 밀리초로 돌려준다."""
    seconds = (finished_at - started_at).total_seconds()
    return int(seconds * MILLISECONDS_PER_SECOND)


class CallStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


# call_model은 비용을 추정하지 않으므로 ESTIMATED가 없다.
class CostStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"


class CostSource(StrEnum):
    API_RESPONSE = "API_RESPONSE"


class CallResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CallStatus
    error_type: ErrorType | None = None
    error_message: str | None = None
    http_status: int | None = None
    failed_routing_step: str | None = None

    content: str | None = None
    finish_reason: str | None = None

    requested_model: str
    actual_model: str | None = None
    provider: str | None = None
    generation_id: str | None = None

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None

    cost_usd: Decimal | None = None
    cost_status: CostStatus = CostStatus.UNKNOWN
    cost_source: CostSource | None = None

    raw_response: dict[str, Any] | None = None

    started_at: datetime
    finished_at: datetime
    latency_ms: int

    @property
    def truncated(self) -> bool:
        return self.finish_reason == TRUNCATED_FINISH_REASON

    @model_validator(mode="after")
    def check_cost_matches_status(self) -> Self:
        # 비용 미확인(UNKNOWN)은 금액이 없는 것과 같은 말이다. 0으로 채우지 않는다.
        if self.cost_status == CostStatus.UNKNOWN and self.cost_usd is not None:
            raise ValueError("비용 상태가 UNKNOWN이면 cost_usd는 비어 있어야 한다")
        if self.cost_status == CostStatus.CONFIRMED and self.cost_usd is None:
            raise ValueError("비용 상태가 CONFIRMED이면 cost_usd가 있어야 한다")
        return self

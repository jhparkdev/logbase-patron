"""연결 테스트 테스트들이 함께 쓰는 가짜 호출기와 호출 결과."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest
from app.openrouter.errors import ErrorType
from app.openrouter.failures import build_failure_result
from app.openrouter.result import CallResult, CallStatus, CostSource, CostStatus

MODEL_ID = "vendor/model-under-test"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
LATENCY_MS = 850
LATENCY = timedelta(milliseconds=LATENCY_MS)


def success(**fields: Any) -> CallResult:
    values: dict[str, Any] = {
        "status": CallStatus.SUCCESS,
        "requested_model": MODEL_ID,
        "actual_model": MODEL_ID,
        "provider": "Io Net",
        "generation_id": "gen-test-1",
        "content": "확인",
        "finish_reason": "stop",
        "prompt_tokens": 18,
        "completion_tokens": 2,
        "total_tokens": 20,
        "cost_usd": Decimal("0.000001"),
        "cost_status": CostStatus.CONFIRMED,
        "cost_source": CostSource.API_RESPONSE,
        "started_at": NOW,
        "finished_at": NOW + LATENCY,
        "latency_ms": LATENCY_MS,
    }
    return CallResult(**{**values, **fields})


def failure(status: CallStatus, error_type: ErrorType, **fields: Any) -> CallResult:
    return build_failure_result(
        status=status,
        error_type=error_type,
        requested_model=MODEL_ID,
        started_at=NOW,
        finished_at=NOW + LATENCY,
        **fields,
    )


class FakeCaller:
    """call_model 대신 정해 둔 결과를 돌려주고, 받은 인자를 기록한다.

    session을 주면 호출되는 순간 호출 이력의 상태를 읽어 둔다(호출 전에 저장됐는지 확인용).
    """

    def __init__(self, result: CallResult, session: AsyncSession | None = None) -> None:
        self.result = result
        self.session = session
        self.calls: list[dict[str, Any]] = []
        self.status_at_call: str | None = None

    async def __call__(self, **kwargs: Any) -> CallResult:
        self.calls.append(kwargs)
        if self.session is not None:
            self.status_at_call = await self.session.scalar(
                select(AIRequest.status).where(
                    AIRequest.request_id == kwargs["request_id"]
                )
            )
        return self.result

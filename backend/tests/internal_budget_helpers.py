"""내부 AI 예산 관리(P-02) 테스트들이 함께 쓰는 도구."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from tests.db_helpers import Factory

# KST 2026-10-01 00:00은 UTC 2026-09-30 15:00이다. 이 시각은 KST 10월 안이다.
IN_OCTOBER = datetime(2026, 10, 10, 3, 0, tzinfo=UTC)
UNKNOWN_COST: dict[str, Any] = {
    "cost_status": "UNKNOWN",
    "cost_usd": None,
    "cost_source": None,
}


async def internal_call(factory: Factory, **values: Any) -> None:
    """기본은 10월 안의 확정 비용 1달러짜리 내부 개발 호출을 하나 넣는다."""
    await factory.ai_request(
        **{
            "usage_origin": "INTERNAL_DEVELOPMENT",
            "requested_at": IN_OCTOBER,
            "cost_status": "CONFIRMED",
            "cost_usd": Decimal(1),
            "cost_source": "API_RESPONSE",
            **values,
        }
    )

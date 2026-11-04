"""AI 도우미의 하루 사용 상한. 시뮬레이터와 같은 OpenRouter Key 한도를 도우미가 다 쓰지 않게 한다.

하루는 KST 날짜다. 금액을 모르는 호출(UNKNOWN)은 더할 수 없어 합계에서 빠지므로, 상한은 확인된 금액 기준이다.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, UsageOrigin
from app.services.simulation_period import DateRange, kst_today, utc_bounds


def daily_limit_reached(spent: Decimal, limit: Decimal) -> bool:
    return spent >= limit


async def spent_today(session: AsyncSession, now: datetime) -> Decimal:
    """오늘(KST) 도우미 호출의 확정·추정 비용 합계."""
    today = kst_today(now)
    start, end = utc_bounds(DateRange(today, today))
    total = await session.scalar(
        select(func.sum(AIRequest.cost_usd)).where(
            AIRequest.usage_origin == UsageOrigin.ASSISTANT.value,
            AIRequest.requested_at >= start,
            AIRequest.requested_at < end,
        )
    )
    return total or Decimal(0)

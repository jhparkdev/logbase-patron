from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.assistant_budget import daily_limit_reached, spent_today
from tests.db_helpers import Factory

# 2026-11-05 12:00 KST
NOW = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
# KST 날짜 경계: 2026-11-05 00:00 KST = 2026-11-04 15:00 UTC
KST_MIDNIGHT = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("spent", "reached"),
    [("0.99", False), ("1", True), ("1.01", True)],
)
def test_한도는_사용액이_한도와_같아지는_순간부터_막는다(
    spent: str, reached: bool
) -> None:
    assert daily_limit_reached(Decimal(spent), Decimal(1)) is reached


async def assistant_call(
    factory: Factory, requested_at: datetime, **values: object
) -> None:
    await factory.ai_request(
        **{
            "usage_origin": "ASSISTANT",
            "requested_at": requested_at,
            "status": "SUCCESS",
            "cost_status": "CONFIRMED",
            "cost_usd": Decimal("0.25"),
            "cost_source": "API_RESPONSE",
            **values,
        }
    )


async def test_오늘_KST_날짜의_도우미_확정_추정_비용만_더한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    price = await factory.model_price()
    await assistant_call(factory, KST_MIDNIGHT)  # 정확히 오늘 0시: 포함
    await assistant_call(factory, NOW)
    await assistant_call(
        factory,
        NOW,
        cost_status="ESTIMATED",
        cost_usd=Decimal("0.5"),
        cost_source="PRICE_ESTIMATE",
        price_id=price["price_id"],
    )
    await assistant_call(
        factory, datetime(2026, 11, 4, 14, 59, 59, tzinfo=UTC)
    )  # 어제 23:59:59 KST: 제외
    await factory.ai_request(
        usage_origin="SIMULATION",
        requested_at=NOW,
        status="SUCCESS",
        cost_status="CONFIRMED",
        cost_usd=Decimal(9),
        cost_source="API_RESPONSE",
    )
    await assistant_call(
        factory, NOW, cost_status="UNKNOWN", cost_usd=None, cost_source=None
    )

    assert await spent_today(db_session, NOW) == Decimal("1.00")


async def test_도우미_호출이_없으면_0이다(db_session: AsyncSession) -> None:
    assert await spent_today(db_session, NOW) == 0

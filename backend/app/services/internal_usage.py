"""내부 AI 예산 관리(P-02) 집계. 내부 출처(개발, 시뮬레이션, 시스템 테스트)의 호출 이력과 구독료를 읽는다.

P-01 집계(aggregation.py)와 같은 규칙이다: 미확인 비용은 금액 합계에 넣지 않고 건수로만 센다.
"""

from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, CostStatus, SubscriptionCost, UsageOrigin
from app.schemas.internal_usage import InternalSummary
from app.services.simulation_period import DateRange, utc_bounds

ZERO = Decimal(0)
# 고객 사용(CUSTOMER_SERVICE)은 내부 비용에 섞지 않는다.
INTERNAL_ORIGINS = (
    UsageOrigin.INTERNAL_DEVELOPMENT.value,
    UsageOrigin.SIMULATION.value,
    UsageOrigin.SYSTEM_TEST.value,
)


def api_conditions(period: DateRange) -> list[ColumnElement[bool]]:
    """기간 안의 내부 호출만 고르는 조건. KST 날짜를 UTC 시각 범위로 바꿔 비교한다."""
    start, end = utc_bounds(period)
    return [
        AIRequest.usage_origin.in_(INTERNAL_ORIGINS),
        AIRequest.requested_at >= start,
        AIRequest.requested_at < end,
    ]


def build_summary(
    confirmed: Decimal, estimated: Decimal, unknown_count: int, subscription: Decimal
) -> InternalSummary:
    return InternalSummary(
        api_confirmed_usd=confirmed,
        api_estimated_usd=estimated,
        subscription_usd=subscription,
        total_managed_usd=confirmed + estimated + subscription,
        unknown_cost_count=unknown_count,
        includes_estimate=estimated > 0,
        has_unknown=unknown_count > 0,
    )


async def summarize(session: AsyncSession, period: DateRange) -> InternalSummary:
    row = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(AIRequest.cost_usd).filter(
                        AIRequest.cost_status == CostStatus.CONFIRMED.value
                    ),
                    ZERO,
                ),
                func.coalesce(
                    func.sum(AIRequest.cost_usd).filter(
                        AIRequest.cost_status == CostStatus.ESTIMATED.value
                    ),
                    ZERO,
                ),
                func.count().filter(AIRequest.cost_status == CostStatus.UNKNOWN.value),
            ).where(*api_conditions(period))
        )
    ).one()
    confirmed, estimated, unknown_count = row
    subscription = await subscription_total(session, period)
    return build_summary(confirmed, estimated, unknown_count, subscription)


async def subscription_total(session: AsyncSession, period: DateRange) -> Decimal:
    """조회 기간이 걸치는 모든 달의 구독료 합계. 달의 일부만 걸쳐도 월 금액 그대로 더한다.

    해지(CANCELLED) 구독료도 그 달 청구액이라 합산한다. 명세에 없는 임시 결정이다.
    """
    first_month = period.start.replace(day=1)
    last_month = period.end.replace(day=1)
    total = await session.scalar(
        select(func.coalesce(func.sum(SubscriptionCost.amount), ZERO)).where(
            SubscriptionCost.applied_month >= first_month,
            SubscriptionCost.applied_month <= last_month,
        )
    )
    return total if total is not None else ZERO

"""내부 AI 예산 관리(P-02) 집계. 내부 출처(개발, 시뮬레이션, 시스템 테스트)의 호출 이력과 구독료를 읽는다.

P-01 집계(aggregation.py)와 같은 규칙이다: 미확인 비용은 금액 합계에 넣지 않고 건수로만 센다.
"""

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, CostStatus, SubscriptionCost, UsageOrigin
from app.schemas.internal_usage import (
    InternalSummary,
    InternalTrend,
    InternalTrendPoint,
)
from app.services.simulation_period import DateRange, utc_bounds

ZERO = Decimal(0)
KST_ZONE = "Asia/Seoul"
# 고객 사용(CUSTOMER_SERVICE)은 내부 비용에 섞지 않는다.
INTERNAL_ORIGINS = (
    UsageOrigin.INTERNAL_DEVELOPMENT.value,
    UsageOrigin.SIMULATION.value,
    UsageOrigin.SYSTEM_TEST.value,
    UsageOrigin.ASSISTANT.value,
)


def api_conditions(
    period: DateRange, project_id: int | None = None, model_id: int | None = None
) -> list[ColumnElement[bool]]:
    """기간 안의 내부 호출만 고르는 조건. KST 날짜를 UTC 시각 범위로 바꿔 비교한다.

    프로젝트나 모델을 주면 그 호출만 고른다.
    """
    start, end = utc_bounds(period)
    conditions = [
        AIRequest.usage_origin.in_(INTERNAL_ORIGINS),
        AIRequest.requested_at >= start,
        AIRequest.requested_at < end,
    ]
    if project_id is not None:
        conditions.append(AIRequest.project_id == project_id)
    if model_id is not None:
        conditions.append(AIRequest.model_id == model_id)
    return conditions


def cost_measures() -> list[Any]:
    """확정 합계, 추정 합계, 미확인 건수. 요약, 추이, 프로젝트 표가 같은 계산을 쓴다."""
    return [
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
    ]


def build_summary(
    confirmed: Decimal,
    estimated: Decimal,
    unknown_count: int,
    subscription: Decimal,
    subscription_excluded: bool = False,
) -> InternalSummary:
    return InternalSummary(
        api_confirmed_usd=confirmed,
        api_estimated_usd=estimated,
        subscription_usd=subscription,
        total_managed_usd=confirmed + estimated + subscription,
        unknown_cost_count=unknown_count,
        includes_estimate=estimated > 0,
        has_unknown=unknown_count > 0,
        subscription_excluded=subscription_excluded,
    )


async def summarize(
    session: AsyncSession,
    period: DateRange,
    project_id: int | None = None,
    model_id: int | None = None,
) -> InternalSummary:
    """프로젝트를 고르면 그 프로젝트에 배분한 구독료만 더한다. 모델을 고르면 구독료는 뺀다."""
    conditions = api_conditions(period, project_id, model_id)
    row = (await session.execute(select(*cost_measures()).where(*conditions))).one()
    confirmed, estimated, unknown_count = row
    excluded = model_id is not None
    subscription = (
        ZERO if excluded else await subscription_total(session, period, project_id)
    )
    return build_summary(confirmed, estimated, unknown_count, subscription, excluded)


def subscription_conditions(
    period: DateRange, project_id: int | None = None
) -> list[ColumnElement[bool]]:
    """조회 기간이 걸치는 모든 달의 구독료를 고르는 조건. 달의 일부만 걸쳐도 그 달 전체를 고른다.

    요약의 구독료 합계와 구독료 목록이 같이 쓴다. 같은 조건의 합계가 서로 일치하게 하기 위해서다.
    프로젝트를 주면 그 프로젝트에 배분한 구독료만 고른다. 배분하지 않은 구독료는 빠진다.
    """
    conditions = [
        SubscriptionCost.applied_month >= period.start.replace(day=1),
        SubscriptionCost.applied_month <= period.end.replace(day=1),
    ]
    if project_id is not None:
        conditions.append(SubscriptionCost.project_id == project_id)
    return conditions


async def subscription_total(
    session: AsyncSession, period: DateRange, project_id: int | None = None
) -> Decimal:
    """조회 기간이 걸치는 모든 달의 구독료 합계. 달의 일부만 걸쳐도 월 금액 그대로 더한다.

    해지(CANCELLED) 구독료도 그 달 청구액이라 합산한다. 명세에 없는 임시 결정이다.
    """
    total = await session.scalar(
        select(func.coalesce(func.sum(SubscriptionCost.amount), ZERO)).where(
            *subscription_conditions(period, project_id)
        )
    )
    return total if total is not None else ZERO


def build_trend(
    period: DateRange, by_day: Mapping[date, tuple[Decimal, Decimal, int]]
) -> InternalTrend:
    """조회 기간의 모든 날짜를 순서대로 담는다. 호출이 없는 날은 0으로 채운다."""
    items = []
    for offset in range((period.end - period.start).days + 1):
        day = period.start + timedelta(days=offset)
        confirmed, estimated, unknown_count = by_day.get(day, (ZERO, ZERO, 0))
        items.append(
            InternalTrendPoint(
                date=day,
                api_confirmed_usd=confirmed,
                api_estimated_usd=estimated,
                unknown_cost_count=unknown_count,
            )
        )
    return InternalTrend(items=items)


async def daily_trend(
    session: AsyncSession,
    period: DateRange,
    project_id: int | None = None,
    model_id: int | None = None,
) -> InternalTrend:
    """KST 날짜별 API 비용. 구독료는 일별로 나누지 않아 넣지 않는다."""
    kst_day = func.timezone(KST_ZONE, AIRequest.requested_at).cast(Date)
    rows = await session.execute(
        select(kst_day, *cost_measures())
        .where(*api_conditions(period, project_id, model_id))
        .group_by(kst_day)
    )
    by_day = {
        day: (confirmed, estimated, unknown_count)
        for day, confirmed, estimated, unknown_count in rows
    }
    return build_trend(period, by_day)

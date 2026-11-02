from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.internal_usage import InternalTrend
from app.services.internal_usage import (
    build_summary,
    build_trend,
    daily_trend,
    summarize,
)
from app.services.simulation_period import DateRange
from tests.db_helpers import Factory
from tests.internal_budget_helpers import IN_OCTOBER, UNKNOWN_COST, internal_call

OCTOBER = DateRange(date(2026, 10, 1), date(2026, 10, 31))
HUNDRED = Decimal(100)
NEXT_DAY = datetime(2026, 10, 11, 3, 0, tzinfo=UTC)


# ---------------------------------------------------------------
# 합계 계산 (DB 없이)
# ---------------------------------------------------------------
def test_총_관리_비용은_확정_추정_구독료의_합이다() -> None:
    summary = build_summary(Decimal(1), Decimal(2), 0, Decimal(3))

    assert summary.total_managed_usd == Decimal(6)
    assert summary.includes_estimate is True
    assert summary.has_unknown is False


def test_추정_비용과_미확인이_없으면_표시_값이_꺼진다() -> None:
    summary = build_summary(Decimal(1), Decimal(0), 0, Decimal(0))

    assert summary.includes_estimate is False
    assert summary.has_unknown is False


def test_미확인이_있으면_합계가_최종이_아니라는_표시가_켜진다() -> None:
    summary = build_summary(Decimal(1), Decimal(0), 2, Decimal(0))

    assert summary.has_unknown is True
    assert summary.unknown_cost_count == 2
    assert summary.total_managed_usd == Decimal(1)


# ---------------------------------------------------------------
# API 비용 (호출 이력)
# ---------------------------------------------------------------
async def test_내부_출처_세_가지만_집계하고_고객_사용은_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    for origin in ("INTERNAL_DEVELOPMENT", "SIMULATION", "SYSTEM_TEST"):
        await internal_call(factory, usage_origin=origin)
    await internal_call(factory, usage_origin="CUSTOMER_SERVICE", cost_usd=HUNDRED)

    summary = await summarize(db_session, OCTOBER)

    assert summary.api_confirmed_usd == Decimal(3)


async def test_확정_추정_미확인을_나누고_미확인은_금액에_넣지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    price = await factory.model_price()
    await internal_call(factory, cost_usd=Decimal(5))
    await internal_call(
        factory,
        cost_status="ESTIMATED",
        cost_usd=Decimal(2),
        cost_source="PRICE_ESTIMATE",
        price_id=price["price_id"],
    )
    await internal_call(factory, **UNKNOWN_COST)
    await internal_call(factory, **UNKNOWN_COST)

    summary = await summarize(db_session, OCTOBER)

    assert summary.api_confirmed_usd == Decimal(5)
    assert summary.api_estimated_usd == Decimal(2)
    assert summary.unknown_cost_count == 2
    assert summary.total_managed_usd == Decimal(7)


@pytest.mark.parametrize(
    ("requested_at", "expected"),
    [
        (datetime(2026, 9, 30, 14, 59, 59, 999999, tzinfo=UTC), 0),
        (datetime(2026, 9, 30, 15, 0, tzinfo=UTC), 1),
        (datetime(2026, 10, 31, 14, 59, 59, 999999, tzinfo=UTC), 1),
        (datetime(2026, 10, 31, 15, 0, tzinfo=UTC), 0),
    ],
    ids=["시작 직전", "시작 정각", "종료일 마지막", "종료 다음 날 0시"],
)
async def test_조회_기간은_KST_날짜_경계를_지킨다(
    db_session: AsyncSession, factory: Factory, requested_at: datetime, expected: int
) -> None:
    await internal_call(factory, requested_at=requested_at)

    summary = await summarize(db_session, OCTOBER)

    assert summary.api_confirmed_usd == Decimal(expected)


async def test_호출이_없으면_모두_0이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    summary = await summarize(db_session, OCTOBER)

    assert summary.api_confirmed_usd == 0
    assert summary.api_estimated_usd == 0
    assert summary.subscription_usd == 0
    assert summary.total_managed_usd == 0
    assert summary.unknown_cost_count == 0
    assert summary.includes_estimate is False
    assert summary.has_unknown is False


# ---------------------------------------------------------------
# 구독료
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (DateRange(date(2026, 10, 1), date(2026, 10, 31)), 10),
        (DateRange(date(2026, 10, 15), date(2026, 10, 20)), 10),
        (DateRange(date(2026, 10, 20), date(2026, 11, 5)), 30),
        (DateRange(date(2026, 9, 1), date(2026, 11, 30)), 70),
        (DateRange(date(2026, 12, 1), date(2026, 12, 31)), 0),
    ],
    ids=["10월 전체", "10월 일부", "10월~11월에 걸침", "9~11월", "구독료 없는 달"],
)
async def test_조회_기간이_걸치는_달의_구독료를_월_금액_그대로_더한다(
    db_session: AsyncSession, factory: Factory, period: DateRange, expected: int
) -> None:
    for month, amount in ((9, 40), (10, 10), (11, 20)):
        await factory.subscription_cost(
            applied_month=date(2026, month, 1), amount=Decimal(amount)
        )

    summary = await summarize(db_session, period)

    assert summary.subscription_usd == Decimal(expected)


async def test_귀속_프로젝트가_없는_구독료도_합산한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1), amount=Decimal(10), project_id=None
    )
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1),
        amount=Decimal(20),
        project_id=project["project_id"],
    )

    summary = await summarize(db_session, OCTOBER)

    assert summary.subscription_usd == Decimal(30)


async def test_해지한_구독료도_그_달_청구액이라_합산한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    # 해지 상태의 처리는 명세에 없어 임시로 정했다. 팀 확인 후 바뀔 수 있다.
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1), amount=Decimal(10), status="CANCELLED"
    )

    summary = await summarize(db_session, OCTOBER)

    assert summary.subscription_usd == Decimal(10)


# ---------------------------------------------------------------
# 일별 추이
# ---------------------------------------------------------------
def test_추이는_조회_기간의_모든_날짜를_순서대로_담고_빈_날은_0이다() -> None:
    period = DateRange(date(2026, 10, 1), date(2026, 10, 3))

    trend = build_trend(period, {date(2026, 10, 2): (Decimal(5), Decimal(2), 1)})

    points = trend.items
    assert [point.date for point in points] == [
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
    ]
    assert [point.api_confirmed_usd for point in points] == [0, 5, 0]
    assert [point.api_estimated_usd for point in points] == [0, 2, 0]
    assert [point.unknown_cost_count for point in points] == [0, 1, 0]


async def test_추이는_날짜별로_확정_추정_미확인을_나눠_센다(
    db_session: AsyncSession, factory: Factory
) -> None:
    price = await factory.model_price()
    await internal_call(factory, requested_at=IN_OCTOBER, cost_usd=Decimal(5))
    await internal_call(
        factory,
        requested_at=IN_OCTOBER,
        cost_status="ESTIMATED",
        cost_usd=Decimal(2),
        cost_source="PRICE_ESTIMATE",
        price_id=price["price_id"],
    )
    await internal_call(factory, requested_at=NEXT_DAY, **UNKNOWN_COST)

    trend = await daily_trend(
        db_session, DateRange(date(2026, 10, 9), date(2026, 10, 12))
    )

    by_date = {point.date: point for point in trend.items}
    assert len(trend.items) == 4
    assert by_date[date(2026, 10, 9)].api_confirmed_usd == 0
    assert by_date[date(2026, 10, 10)].api_confirmed_usd == Decimal(5)
    assert by_date[date(2026, 10, 10)].api_estimated_usd == Decimal(2)
    assert by_date[date(2026, 10, 11)].unknown_cost_count == 1
    assert by_date[date(2026, 10, 11)].api_confirmed_usd == 0


@pytest.mark.parametrize(
    ("requested_at", "expected_day"),
    [
        (datetime(2026, 10, 10, 14, 59, 59, 999999, tzinfo=UTC), date(2026, 10, 10)),
        (datetime(2026, 10, 10, 15, 0, tzinfo=UTC), date(2026, 10, 11)),
    ],
    ids=["KST 23시 59분", "KST 다음 날 0시"],
)
async def test_추이의_날짜는_KST_달력_기준이다(
    db_session: AsyncSession,
    factory: Factory,
    requested_at: datetime,
    expected_day: date,
) -> None:
    await internal_call(factory, requested_at=requested_at)

    trend = await daily_trend(
        db_session, DateRange(date(2026, 10, 10), date(2026, 10, 11))
    )

    counted = [point.date for point in trend.items if point.api_confirmed_usd > 0]
    assert counted == [expected_day]


async def test_추이도_고객_사용은_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await internal_call(factory, usage_origin="CUSTOMER_SERVICE", cost_usd=HUNDRED)

    trend = await daily_trend(db_session, OCTOBER)

    assert all(point.api_confirmed_usd == 0 for point in trend.items)


# ---------------------------------------------------------------
# 프로젝트·모델 조건
# ---------------------------------------------------------------
def total_of(trend: InternalTrend) -> Decimal:
    return sum((point.api_confirmed_usd for point in trend.items), Decimal(0))


async def test_프로젝트를_고르면_그_프로젝트의_호출과_귀속_구독료만_집계한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    mine = await factory.project()
    other = await factory.project()
    await internal_call(factory, project_id=mine["project_id"], cost_usd=Decimal(2))
    await internal_call(factory, project_id=other["project_id"], cost_usd=Decimal(5))
    await internal_call(factory, project_id=mine["project_id"], **UNKNOWN_COST)
    month = date(2026, 10, 1)
    await factory.subscription_cost(
        applied_month=month, amount=Decimal(10), project_id=mine["project_id"]
    )
    await factory.subscription_cost(
        applied_month=month, amount=Decimal(20), project_id=other["project_id"]
    )
    # 어느 프로젝트에도 배분하지 않은 구독료는 프로젝트를 고르면 빠진다.
    await factory.subscription_cost(applied_month=month, amount=Decimal(40))

    summary = await summarize(db_session, OCTOBER, project_id=mine["project_id"])

    assert summary.api_confirmed_usd == Decimal(2)
    assert summary.unknown_cost_count == 1
    assert summary.subscription_usd == Decimal(10)
    assert summary.total_managed_usd == Decimal(12)
    assert summary.subscription_excluded is False


async def test_모델을_고르면_그_모델의_호출만_집계하고_구독료는_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model()
    other = await factory.model()
    await internal_call(factory, model_id=model["model_id"], cost_usd=Decimal(2))
    await internal_call(factory, model_id=other["model_id"], cost_usd=Decimal(5))
    await factory.subscription_cost(applied_month=date(2026, 10, 1), amount=Decimal(10))

    summary = await summarize(db_session, OCTOBER, model_id=model["model_id"])

    assert summary.api_confirmed_usd == Decimal(2)
    assert summary.subscription_usd == 0
    assert summary.total_managed_usd == Decimal(2)
    assert summary.subscription_excluded is True


async def test_프로젝트와_모델을_함께_고르면_둘_다_맞는_호출만_집계하고_구독료는_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    model = await factory.model()
    await internal_call(
        factory,
        project_id=project["project_id"],
        model_id=model["model_id"],
        cost_usd=Decimal(2),
    )
    await internal_call(factory, project_id=project["project_id"], cost_usd=Decimal(3))
    await internal_call(factory, model_id=model["model_id"], cost_usd=Decimal(4))
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1),
        amount=Decimal(10),
        project_id=project["project_id"],
    )

    summary = await summarize(
        db_session,
        OCTOBER,
        project_id=project["project_id"],
        model_id=model["model_id"],
    )

    assert summary.api_confirmed_usd == Decimal(2)
    assert summary.subscription_usd == 0
    assert summary.subscription_excluded is True


async def test_조건이_없으면_구독료를_빼지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.subscription_cost(applied_month=date(2026, 10, 1), amount=Decimal(10))

    summary = await summarize(db_session, OCTOBER)

    assert summary.subscription_usd == Decimal(10)
    assert summary.subscription_excluded is False


async def test_추이도_프로젝트와_모델_조건을_따른다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    model = await factory.model()
    other = await factory.model()
    await internal_call(
        factory,
        project_id=project["project_id"],
        model_id=model["model_id"],
        cost_usd=Decimal(2),
    )
    await internal_call(factory, model_id=other["model_id"], cost_usd=Decimal(5))

    by_project = await daily_trend(
        db_session, OCTOBER, project_id=project["project_id"]
    )
    by_model = await daily_trend(db_session, OCTOBER, model_id=other["model_id"])

    assert total_of(by_project) == Decimal(2)
    assert total_of(by_model) == Decimal(5)

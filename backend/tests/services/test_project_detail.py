from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.budget_policy import BudgetStatus
from app.services.project_budgets import project_budget_rows
from app.services.project_detail import project_detail
from tests.db_helpers import Factory
from tests.internal_budget_helpers import UNKNOWN_COST, internal_call

OCT = date(2026, 10, 1)


async def test_없는_프로젝트는_None이다(db_session: AsyncSession) -> None:
    assert await project_detail(db_session, 987654, OCT) is None


async def test_호출과_예산이_없으면_0이고_예산은_미설정이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project(name="빈 프로젝트")

    detail = await project_detail(db_session, project["project_id"], OCT)

    assert detail is not None
    assert detail.project_name == "빈 프로젝트"
    assert detail.month == OCT
    assert detail.call_count == 0
    assert detail.subscription_usd == 0
    assert detail.budget.monthly_amount_usd is None
    assert detail.budget.effective_from_month is None
    assert detail.budget.status == BudgetStatus.UNSET
    assert detail.services == []
    assert detail.subscriptions == []


async def test_합계와_예산_현황과_서비스별_사용량과_구독료를_돌려준다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    project_id = project["project_id"]
    price = await factory.model_price()
    service_a = await factory.service(name="서비스 A")
    service_b = await factory.service(name="서비스 B")
    await factory.budget(project_id=project_id, monthly_amount_usd=Decimal(100))
    await internal_call(
        factory,
        project_id=project_id,
        service_id=service_a["service_id"],
        cost_usd=Decimal(10),
    )
    await internal_call(
        factory,
        project_id=project_id,
        service_id=service_b["service_id"],
        cost_status="ESTIMATED",
        cost_usd=Decimal(20),
        cost_source="PRICE_ESTIMATE",
        price_id=price["price_id"],
    )
    await internal_call(
        factory,
        project_id=project_id,
        service_id=service_b["service_id"],
        **UNKNOWN_COST,
    )
    await factory.subscription_cost(
        applied_month=OCT,
        amount=Decimal(30),
        project_id=project_id,
        tool_name="도구 가",
    )

    detail = await project_detail(db_session, project_id, OCT)

    assert detail is not None
    assert detail.call_count == 3
    assert detail.confirmed_cost_usd == Decimal(10)
    assert detail.estimated_cost_usd == Decimal(20)
    assert detail.subscription_usd == Decimal(30)
    assert detail.unknown_cost_count == 1
    budget = detail.budget
    assert budget.month == OCT
    assert budget.monthly_amount_usd == Decimal(100)
    assert budget.effective_from_month == date(2026, 10, 1)
    assert budget.used_usd == Decimal(60)
    assert budget.usage_pct == Decimal("60.00")
    assert budget.confirmed_usage_pct == Decimal("40.00")
    assert budget.remaining_usd == Decimal(40)
    assert budget.unknown_cost_count == 1
    assert budget.status == BudgetStatus.NORMAL
    assert [item.service_name for item in detail.services] == ["서비스 A", "서비스 B"]
    assert [item.budget_share_pct for item in detail.services] == [
        Decimal("10.00"),
        Decimal("20.00"),
    ]
    assert [item.unknown_cost_count for item in detail.services] == [0, 1]
    assert [item.call_count for item in detail.services] == [1, 2]
    assert [(item.tool_name, item.amount_usd) for item in detail.subscriptions] == [
        ("도구 가", Decimal(30))
    ]


async def test_예산이_없으면_서비스별_비중이_null이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    await internal_call(factory, project_id=project["project_id"])

    detail = await project_detail(db_session, project["project_id"], OCT)

    assert detail is not None
    assert [item.budget_share_pct for item in detail.services] == [None]


async def test_해지된_구독료도_목록에_상태와_함께_나오고_합계에_들어간다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    project_id = project["project_id"]
    await factory.subscription_cost(
        applied_month=OCT, amount=Decimal(10), project_id=project_id
    )
    await factory.subscription_cost(
        applied_month=OCT, amount=Decimal(5), project_id=project_id, status="CANCELLED"
    )

    detail = await project_detail(db_session, project_id, OCT)

    assert detail is not None
    assert detail.subscription_usd == Decimal(15)
    assert [item.status for item in detail.subscriptions] == ["ACTIVE", "CANCELLED"]


async def test_다른_달_다른_프로젝트_미배분_구독료는_넣지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    other = await factory.project()
    project_id = project["project_id"]
    await internal_call(factory, project_id=other["project_id"], cost_usd=Decimal(500))
    await internal_call(
        factory,
        project_id=project_id,
        requested_at=datetime(2026, 9, 10, 3, 0, tzinfo=UTC),
        cost_usd=Decimal(1000),
    )
    await factory.subscription_cost(applied_month=OCT, amount=Decimal(1000))
    await factory.subscription_cost(
        applied_month=date(2026, 9, 1), amount=Decimal(1000), project_id=project_id
    )

    detail = await project_detail(db_session, project_id, OCT)

    assert detail is not None
    assert detail.call_count == 0
    assert detail.budget.used_usd == 0
    assert detail.subscriptions == []


async def test_작업_수는_서로_다른_작업만_센다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    project_id = project["project_id"]
    first = await factory.task(project_id=project_id)
    second = await factory.task(project_id=project_id)
    for task in (first, first, second):
        await internal_call(factory, project_id=project_id, task_id=task["task_id"])

    detail = await project_detail(db_session, project_id, OCT)

    assert detail is not None
    assert detail.call_count == 3
    assert detail.task_count == 2


@pytest.mark.parametrize(
    ("from_month", "to_month", "applies"),
    [
        (date(2026, 10, 1), None, True),
        (date(2026, 11, 1), None, False),
        (date(2026, 8, 1), date(2026, 9, 1), False),
        (date(2026, 8, 1), date(2026, 10, 1), True),
    ],
    ids=["시작 월", "시작 월이 다음 달", "종료 월이 전달", "종료 월이 그 달"],
)
async def test_예산은_적용_기간_안의_달에만_보인다(
    db_session: AsyncSession,
    factory: Factory,
    from_month: date,
    to_month: date | None,
    applies: bool,
) -> None:
    project = await factory.project()
    await factory.budget(
        project_id=project["project_id"],
        effective_from_month=from_month,
        effective_to_month=to_month,
    )

    detail = await project_detail(db_session, project["project_id"], OCT)

    assert detail is not None
    assert (detail.budget.monthly_amount_usd is not None) is applies


async def test_표의_한_행과_사용액_상태가_같다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    project_id = project["project_id"]
    await factory.budget(project_id=project_id, monthly_amount_usd=Decimal(100))
    await internal_call(factory, project_id=project_id, cost_usd=Decimal(70))
    await internal_call(factory, project_id=project_id, **UNKNOWN_COST)
    await factory.subscription_cost(
        applied_month=OCT, amount=Decimal(15), project_id=project_id
    )

    detail = await project_detail(db_session, project_id, OCT)
    rows = await project_budget_rows(db_session, OCT)

    row = next(item for item in rows if item.project_id == project_id)
    assert detail is not None
    assert detail.budget.used_usd == row.used_usd
    assert detail.budget.usage_pct == row.usage_pct
    assert detail.budget.status == row.status == BudgetStatus.WARNING
    assert detail.unknown_cost_count == row.unknown_cost_count

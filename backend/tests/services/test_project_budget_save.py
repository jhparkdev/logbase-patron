"""프로젝트 월 예산 등록·수정 테스트. 수정은 이전 달까지의 예산을 남기고 새 행을 추가한다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, ChangeLog
from app.services.project_budget_save import (
    ProjectBudgetConflictError,
    ProjectNotFoundError,
    save_project_budget,
)
from tests.db_helpers import Factory

SEPTEMBER = date(2026, 9, 1)
OCTOBER = date(2026, 10, 1)
NOVEMBER = date(2026, 11, 1)


@pytest.fixture
async def project_id(factory: Factory) -> int:
    return (await factory.project())["project_id"]


@pytest.fixture
async def user_id(factory: Factory) -> int:
    return (await factory.user())["user_id"]


async def existing_budget(
    factory: Factory, project_id: int, **values: Any
) -> dict[str, Any]:
    row = await factory.budget(
        project_id=project_id,
        monthly_amount_usd=Decimal(10),
        effective_from_month=OCTOBER,
        **values,
    )
    return dict(row)


async def budgets_of(session: AsyncSession, project_id: int) -> list[Budget]:
    session.expire_all()
    rows = await session.scalars(
        select(Budget)
        .where(Budget.project_id == project_id)
        .order_by(Budget.effective_from_month)
    )
    return list(rows)


async def logs_of(session: AsyncSession, budget_id: int) -> list[ChangeLog]:
    rows = await session.scalars(
        select(ChangeLog)
        .where(
            ChangeLog.entity_type == "budgets", ChangeLog.entity_id == str(budget_id)
        )
        .order_by(ChangeLog.log_id)
    )
    return list(rows)


async def test_첫_예산은_종료_월_없이_추가하고_이력을_남긴다(
    db_session: AsyncSession, project_id: int, user_id: int
) -> None:
    saved = await save_project_budget(
        db_session, project_id, Decimal(20), OCTOBER, user_id
    )

    assert saved.scope_type == "PROJECT"
    assert saved.project_id == project_id
    assert saved.customer_id is None
    assert saved.effective_from_month == OCTOBER
    assert saved.effective_to_month is None
    assert saved.created_by == user_id
    logs = await logs_of(db_session, saved.budget_id)
    assert [log.action for log in logs] == ["CREATE"]
    assert logs[0].changed_by == user_id


async def test_더_늦은_시작_월이면_기존_예산을_전월로_끝내고_새_예산을_추가한다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    old = await existing_budget(factory, project_id)

    saved = await save_project_budget(
        db_session, project_id, Decimal(20), NOVEMBER, user_id
    )

    rows = await budgets_of(db_session, project_id)
    assert [
        (row.effective_from_month, row.effective_to_month, row.monthly_amount_usd)
        for row in rows
    ] == [(OCTOBER, OCTOBER, Decimal(10)), (NOVEMBER, None, Decimal(20))]
    assert saved.budget_id == rows[1].budget_id
    closed = await logs_of(db_session, old["budget_id"])
    assert closed[0].action == "UPDATE"
    assert closed[0].changes["effective_to_month"] == {
        "old": None,
        "new": "2026-10-01",
    }


async def test_같은_시작_월이면_금액만_바꾸고_이력을_남긴다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    old = await existing_budget(factory, project_id)

    saved = await save_project_budget(
        db_session, project_id, Decimal(30), OCTOBER, user_id
    )

    rows = await budgets_of(db_session, project_id)
    assert len(rows) == 1
    assert saved.budget_id == old["budget_id"]
    assert rows[0].monthly_amount_usd == Decimal(30)
    assert rows[0].updated_by == user_id
    logs = await logs_of(db_session, old["budget_id"])
    assert logs[0].action == "UPDATE"
    assert Decimal(logs[0].changes["monthly_amount_usd"]["old"]) == Decimal(10)
    assert Decimal(logs[0].changes["monthly_amount_usd"]["new"]) == Decimal(30)


async def test_같은_금액을_다시_저장하면_아무것도_바뀌지_않는다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    old = await existing_budget(factory, project_id)

    await save_project_budget(db_session, project_id, Decimal(10), OCTOBER, user_id)

    assert await logs_of(db_session, old["budget_id"]) == []


async def test_더_이른_시작_월은_거절하고_아무것도_바꾸지_않는다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    await existing_budget(factory, project_id)

    with pytest.raises(ProjectBudgetConflictError):
        await save_project_budget(
            db_session, project_id, Decimal(20), SEPTEMBER, user_id
        )

    rows = await budgets_of(db_session, project_id)
    assert len(rows) == 1
    assert rows[0].effective_from_month == OCTOBER


async def test_예정된_예산보다_앞선_달은_거절한다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    await factory.budget(
        project_id=project_id,
        effective_from_month=SEPTEMBER,
        effective_to_month=SEPTEMBER,
    )
    await factory.budget(project_id=project_id, effective_from_month=NOVEMBER)

    with pytest.raises(ProjectBudgetConflictError):
        await save_project_budget(db_session, project_id, Decimal(20), OCTOBER, user_id)


async def test_이미_끝난_예산_뒤의_달은_새_예산만_추가한다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    await factory.budget(
        project_id=project_id,
        effective_from_month=SEPTEMBER,
        effective_to_month=SEPTEMBER,
    )

    await save_project_budget(db_session, project_id, Decimal(20), NOVEMBER, user_id)

    rows = await budgets_of(db_session, project_id)
    assert rows[0].effective_to_month == SEPTEMBER
    assert rows[1].effective_from_month == NOVEMBER


async def test_다른_프로젝트와_고객의_예산은_건드리지_않는다(
    db_session: AsyncSession, factory: Factory, project_id: int, user_id: int
) -> None:
    other = await factory.project()
    await existing_budget(factory, other["project_id"])
    await factory.budget(scope_type="CUSTOMER")

    await save_project_budget(db_session, project_id, Decimal(20), NOVEMBER, user_id)

    db_session.expire_all()
    untouched = await db_session.scalars(
        select(Budget).where(Budget.project_id.is_distinct_from(project_id))
    )
    assert [row.effective_to_month for row in untouched] == [None, None]


async def test_없는_프로젝트의_예산은_저장하지_않고_거절한다(
    db_session: AsyncSession, user_id: int
) -> None:
    with pytest.raises(ProjectNotFoundError):
        await save_project_budget(db_session, 987654, Decimal(20), OCTOBER, user_id)

"""고객 예산 등록·수정 테스트. 수정은 이전 달까지의 예산을 남기고 새 행을 추가한다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, ChangeLog
from app.services.customer_budgets import (
    BudgetPeriodConflictError,
    CustomerNotFoundError,
    save_customer_budget,
)
from tests.db_helpers import Factory

SEPTEMBER = date(2026, 9, 1)
OCTOBER = date(2026, 10, 1)
NOVEMBER = date(2026, 11, 1)


@pytest.fixture
async def customer_id(factory: Factory) -> int:
    return (await factory.customer())["customer_id"]


@pytest.fixture
async def user_id(factory: Factory) -> int:
    return (await factory.user())["user_id"]


async def existing_budget(
    factory: Factory, customer_id: int, **values: Any
) -> dict[str, Any]:
    row = await factory.budget(
        scope_type="CUSTOMER",
        customer_id=customer_id,
        monthly_amount_usd=Decimal(10),
        effective_from_month=OCTOBER,
        **values,
    )
    return dict(row)


async def budgets_of(session: AsyncSession, customer_id: int) -> list[Budget]:
    session.expire_all()
    rows = await session.scalars(
        select(Budget)
        .where(Budget.customer_id == customer_id)
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


async def test_first_budget_is_added_without_an_end_month(
    db_session: AsyncSession, customer_id: int, user_id: int
) -> None:
    saved = await save_customer_budget(
        db_session, customer_id, Decimal(20), OCTOBER, user_id
    )

    assert saved.effective_from_month == OCTOBER
    assert saved.effective_to_month is None
    assert saved.created_by == user_id
    assert saved.scope_type == "CUSTOMER"
    logs = await logs_of(db_session, saved.budget_id)
    assert [log.action for log in logs] == ["CREATE"]
    assert logs[0].changed_by == user_id


async def test_later_start_month_closes_the_old_budget_and_adds_a_new_one(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    old = await existing_budget(factory, customer_id)

    saved = await save_customer_budget(
        db_session, customer_id, Decimal(20), NOVEMBER, user_id
    )

    rows = await budgets_of(db_session, customer_id)
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


async def test_same_start_month_changes_only_the_amount_and_records_it(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    old = await existing_budget(factory, customer_id)

    saved = await save_customer_budget(
        db_session, customer_id, Decimal(30), OCTOBER, user_id
    )

    rows = await budgets_of(db_session, customer_id)
    assert len(rows) == 1
    assert saved.budget_id == old["budget_id"]
    assert rows[0].monthly_amount_usd == Decimal(30)
    assert rows[0].updated_by == user_id
    logs = await logs_of(db_session, old["budget_id"])
    assert logs[0].action == "UPDATE"
    assert Decimal(logs[0].changes["monthly_amount_usd"]["old"]) == Decimal(10)
    assert Decimal(logs[0].changes["monthly_amount_usd"]["new"]) == Decimal(30)


async def test_saving_the_same_amount_changes_nothing(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    old = await existing_budget(factory, customer_id)

    await save_customer_budget(db_session, customer_id, Decimal(10), OCTOBER, user_id)

    assert await logs_of(db_session, old["budget_id"]) == []


async def test_earlier_start_month_is_rejected_and_nothing_changes(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    await existing_budget(factory, customer_id)

    with pytest.raises(BudgetPeriodConflictError):
        await save_customer_budget(
            db_session, customer_id, Decimal(20), SEPTEMBER, user_id
        )

    rows = await budgets_of(db_session, customer_id)
    assert len(rows) == 1
    assert rows[0].effective_from_month == OCTOBER


async def test_month_before_a_scheduled_budget_is_rejected(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    await factory.budget(
        scope_type="CUSTOMER",
        customer_id=customer_id,
        effective_from_month=SEPTEMBER,
        effective_to_month=SEPTEMBER,
    )
    await factory.budget(
        scope_type="CUSTOMER",
        customer_id=customer_id,
        effective_from_month=NOVEMBER,
    )

    with pytest.raises(BudgetPeriodConflictError):
        await save_customer_budget(
            db_session, customer_id, Decimal(20), OCTOBER, user_id
        )


async def test_month_after_an_ended_budget_only_adds_a_new_one(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    await factory.budget(
        scope_type="CUSTOMER",
        customer_id=customer_id,
        effective_from_month=SEPTEMBER,
        effective_to_month=SEPTEMBER,
    )

    await save_customer_budget(db_session, customer_id, Decimal(20), NOVEMBER, user_id)

    rows = await budgets_of(db_session, customer_id)
    assert rows[0].effective_to_month == SEPTEMBER
    assert rows[1].effective_from_month == NOVEMBER


async def test_other_customers_budgets_are_untouched(
    db_session: AsyncSession, factory: Factory, customer_id: int, user_id: int
) -> None:
    other = await factory.customer()
    await existing_budget(factory, other["customer_id"])

    await save_customer_budget(db_session, customer_id, Decimal(20), NOVEMBER, user_id)

    rows = await budgets_of(db_session, other["customer_id"])
    assert rows[0].effective_to_month is None


async def test_unknown_customer_is_rejected(
    db_session: AsyncSession, user_id: int
) -> None:
    with pytest.raises(CustomerNotFoundError):
        await save_customer_budget(db_session, 987654, Decimal(20), OCTOBER, user_id)

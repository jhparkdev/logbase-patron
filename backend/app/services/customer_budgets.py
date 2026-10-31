"""고객 월 예산 등록·수정. 지난달까지의 예산은 그대로 남기고 변경 이력을 change_logs에 쓴다.

- 기존 시작 월보다 늦으면: 기존 예산을 전월로 끝내고 새 행을 추가한다.
- 기존 시작 월과 같으면: 금액만 바꾼다(겹침 제약 때문에 같은 달에 새 행을 넣을 수 없다).
- 그 밖에 뒤따르는 예산과 겹치면: 거절한다.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, BudgetScopeType, ChangeAction, ChangeLog, Customer

ENTITY_TYPE = "budgets"
CREATE_REASON = "고객 월 예산 등록"
AMOUNT_REASON = "고객 월 예산 금액 수정"
CLOSE_REASON = "새 고객 월 예산 적용으로 종료"


class CustomerNotFoundError(LookupError):
    """예산을 저장할 고객이 없다."""


class BudgetPeriodConflictError(ValueError):
    """적용 시작 월이 다른 예산의 기간과 겹친다."""


async def save_customer_budget(
    session: AsyncSession,
    customer_id: int,
    amount: Decimal,
    start_month: date,
    user_id: int,
) -> Budget:
    # 같은 고객의 동시 저장을 줄 세운다. 호출 기록의 외래키 검사는 막지 않는 잠금이다
    customer = await session.scalar(
        select(Customer.customer_id)
        .where(Customer.customer_id == customer_id)
        .with_for_update(key_share=True)
    )
    if customer is None:
        raise CustomerNotFoundError
    budgets = list(
        await session.scalars(
            select(Budget)
            .where(
                Budget.scope_type == BudgetScopeType.CUSTOMER.value,
                Budget.customer_id == customer_id,
            )
            .order_by(Budget.effective_from_month)
        )
    )
    same_month = next(
        (row for row in budgets if row.effective_from_month == start_month), None
    )
    if same_month is not None:
        saved = _change_amount(session, same_month, amount, user_id)
    elif any(row.effective_from_month > start_month for row in budgets):
        raise BudgetPeriodConflictError
    else:
        saved = await _add_budget(
            session, budgets, customer_id, amount, start_month, user_id
        )
    await session.commit()
    return saved


def _change_amount(
    session: AsyncSession, budget: Budget, amount: Decimal, user_id: int
) -> Budget:
    if budget.monthly_amount_usd == amount:
        return budget
    old_amount = budget.monthly_amount_usd
    budget.monthly_amount_usd = amount
    budget.updated_by = user_id
    _log(
        session,
        budget.budget_id,
        ChangeAction.UPDATE,
        {"monthly_amount_usd": {"old": str(old_amount), "new": str(amount)}},
        AMOUNT_REASON,
        user_id,
    )
    return budget


async def _add_budget(
    session: AsyncSession,
    budgets: list[Budget],
    customer_id: int,
    amount: Decimal,
    start_month: date,
    user_id: int,
) -> Budget:
    for budget in budgets:
        ends_after_start = (
            budget.effective_to_month is None
            or budget.effective_to_month >= start_month
        )
        if ends_after_start:
            _close(session, budget, _previous_month(start_month), user_id)
    # 기존 행을 먼저 끝내야 새 행이 겹침 제약에 걸리지 않는다
    await session.flush()
    new_budget = Budget(
        scope_type=BudgetScopeType.CUSTOMER.value,
        customer_id=customer_id,
        monthly_amount_usd=amount,
        effective_from_month=start_month,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(new_budget)
    await session.flush()
    _log(
        session,
        new_budget.budget_id,
        ChangeAction.CREATE,
        {
            "monthly_amount_usd": {"old": None, "new": str(amount)},
            "effective_from_month": {"old": None, "new": start_month.isoformat()},
        },
        CREATE_REASON,
        user_id,
    )
    return new_budget


def _close(
    session: AsyncSession, budget: Budget, last_month: date, user_id: int
) -> None:
    old_end = budget.effective_to_month
    budget.effective_to_month = last_month
    budget.updated_by = user_id
    _log(
        session,
        budget.budget_id,
        ChangeAction.UPDATE,
        {
            "effective_to_month": {
                "old": old_end.isoformat() if old_end else None,
                "new": last_month.isoformat(),
            }
        },
        CLOSE_REASON,
        user_id,
    )


def _previous_month(month: date) -> date:
    return (month - timedelta(days=1)).replace(day=1)


def _log(
    session: AsyncSession,
    budget_id: int,
    action: ChangeAction,
    changes: dict[str, Any],
    reason: str,
    user_id: int,
) -> None:
    session.add(
        ChangeLog(
            entity_type=ENTITY_TYPE,
            entity_id=str(budget_id),
            action=action.value,
            changes=changes,
            reason=reason,
            changed_by=user_id,
        )
    )

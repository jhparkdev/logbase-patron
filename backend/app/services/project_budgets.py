"""내부 프로젝트의 월 예산 현황(P-02).

사용액 = 그 달의 API 비용(확정 + 추정) + 그 프로젝트에 귀속된 구독료다.
미확인 호출은 금액을 모르므로 넣지 않고 건수로만 센다.
프로젝트에 귀속되지 않은 구독료(미배분)는 어느 프로젝트의 사용액에도 넣지 않는다.
"""

from collections.abc import Callable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, Budget, BudgetScopeType, Project, SubscriptionCost
from app.schemas.models import SortOrder
from app.schemas.project_budget import (
    ProjectBudgetPage,
    ProjectBudgetRow,
    ProjectRowSort,
    ProjectRowsQuery,
)
from app.services.budget_policy import BudgetStatus, evaluate_budget
from app.services.internal_usage import ZERO, api_conditions, cost_measures
from app.services.simulation_period import DateRange

# 요약 화면의 미리보기 건수
PROJECT_PREVIEW_ROWS = 5
# 상태 정렬 순서는 심각한 정도다. 미설정은 값이 없어 어느 방향이든 맨 뒤에 둔다
STATUS_SEVERITY = {
    BudgetStatus.NORMAL: 0,
    BudgetStatus.WARNING: 1,
    BudgetStatus.OVER: 2,
}
SORT_KEYS: dict[ProjectRowSort, Callable[[ProjectBudgetRow], Any]] = {
    ProjectRowSort.PROJECT: lambda row: row.project_name,
    ProjectRowSort.BUDGET: lambda row: row.monthly_amount_usd,
    ProjectRowSort.USED: lambda row: row.used_usd,
    ProjectRowSort.USAGE: lambda row: row.usage_pct,
    ProjectRowSort.STATUS: lambda row: STATUS_SEVERITY.get(row.status),
}


def month_period(month: date) -> DateRange:
    first = month.replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    return DateRange(first, next_month - timedelta(days=1))


def budget_conditions(month: date) -> list[ColumnElement[bool]]:
    """그 달에 적용되는 프로젝트 예산을 고르는 조건. 표와 상세가 같이 쓴다."""
    return [
        Budget.scope_type == BudgetScopeType.PROJECT.value,
        Budget.effective_from_month <= month,
        or_(
            Budget.effective_to_month.is_(None),
            Budget.effective_to_month >= month,
        ),
    ]


def build_row(
    project_id: int,
    name: str,
    monthly_amount: Decimal | None,
    api_confirmed: Decimal,
    api_estimated: Decimal,
    subscription: Decimal,
    unknown_count: int,
) -> ProjectBudgetRow:
    # 구독료는 청구액이 정해진 금액이라 확정 쪽에 더한다
    evaluation = evaluate_budget(
        monthly_amount, api_confirmed + subscription, api_estimated
    )
    return ProjectBudgetRow(
        project_id=project_id,
        project_name=name,
        monthly_amount_usd=monthly_amount,
        used_usd=evaluation.used_usd,
        usage_pct=evaluation.usage_pct,
        status=evaluation.status,
        unknown_cost_count=unknown_count,
    )


async def project_budget_rows(
    session: AsyncSession,
    month: date,
    project_id: int | None = None,
    model_id: int | None = None,
) -> list[ProjectBudgetRow]:
    """사용 중인 모든 프로젝트의 그 달 예산 현황. 호출이 없는 프로젝트도 0으로 나온다.

    프로젝트를 고르면 그 프로젝트 한 행만 나온다. 모델을 고르면 그 모델의 호출만 사용액이고
    구독료는 뺀다(요약과 같은 규칙이다).
    """
    projects_statement = select(Project.project_id, Project.name).where(
        Project.is_active
    )
    if project_id is not None:
        projects_statement = projects_statement.where(Project.project_id == project_id)
    projects = (await session.execute(projects_statement)).all()
    usage_rows = await session.execute(
        select(AIRequest.project_id, *cost_measures())
        .where(*api_conditions(month_period(month), project_id, model_id))
        .group_by(AIRequest.project_id)
    )
    usage = {
        owner: (confirmed, estimated, unknown_count)
        for owner, confirmed, estimated, unknown_count in usage_rows
    }
    subscriptions: dict[int, Decimal] = {}
    if model_id is None:
        subscription_rows = await session.execute(
            select(SubscriptionCost.project_id, func.sum(SubscriptionCost.amount))
            .where(
                SubscriptionCost.applied_month == month.replace(day=1),
                SubscriptionCost.project_id.is_not(None),
            )
            .group_by(SubscriptionCost.project_id)
        )
        subscriptions = {owner: total for owner, total in subscription_rows}
    budget_rows = await session.scalars(select(Budget).where(*budget_conditions(month)))
    budgets = {budget.project_id: budget.monthly_amount_usd for budget in budget_rows}

    rows = []
    for owner, name in projects:
        confirmed, estimated, unknown_count = usage.get(owner, (ZERO, ZERO, 0))
        rows.append(
            build_row(
                owner,
                name,
                budgets.get(owner),
                confirmed,
                estimated,
                subscriptions.get(owner, ZERO),
                unknown_count,
            )
        )
    return rows


def sort_rows(
    rows: Sequence[ProjectBudgetRow], sort: ProjectRowSort, descending: bool
) -> list[ProjectBudgetRow]:
    """값이 없는 행(예산 미설정)은 정렬 방향과 관계없이 맨 뒤에 두고 사용액이 큰 순서로 놓는다.

    값이 있는 행의 같은 값은 프로젝트 이름순이다.
    """
    key = SORT_KEYS[sort]
    by_name = sorted(rows, key=lambda row: (row.project_name, row.project_id))
    present = [row for row in by_name if key(row) is not None]
    # 사용액이 같으면 이미 이름순이고, 파이썬 정렬은 같은 값의 순서를 바꾸지 않는다
    missing = sorted(
        (row for row in by_name if key(row) is None),
        key=lambda row: row.used_usd,
        reverse=True,
    )
    return sorted(present, key=key, reverse=descending) + missing


def page_rows(
    rows: Sequence[ProjectBudgetRow], query: ProjectRowsQuery
) -> list[ProjectBudgetRow]:
    descending = query.order == SortOrder.DESC
    if query.preview:
        # 사용률이 높은 N개를 먼저 고른다. 정렬해도 "상위 N개"의 뜻이 바뀌지 않게 하기 위해서다.
        # 예산이 없는 프로젝트는 사용률이 없어 예산이 있는 프로젝트 뒤에서 사용액 순으로 채워진다
        top = sort_rows(rows, ProjectRowSort.USAGE, True)[:PROJECT_PREVIEW_ROWS]
        return sort_rows(top, query.sort, descending)
    ordered = sort_rows(rows, query.sort, descending)
    start = (query.page - 1) * query.page_size
    return ordered[start : start + query.page_size]


async def list_project_budgets(
    session: AsyncSession, query: ProjectRowsQuery
) -> ProjectBudgetPage:
    """행 수가 프로젝트 수로 작아 메모리에서 정렬한다. 상태 정렬이 판단 함수의 결과를 그대로 쓰게 하기 위해서다."""
    rows = await project_budget_rows(
        session, query.month, query.project_id, query.model_id
    )
    return ProjectBudgetPage(
        items=page_rows(rows, query),
        total=len(rows),
        page=query.page,
        page_size=query.page_size,
    )

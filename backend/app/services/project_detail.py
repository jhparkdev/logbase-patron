"""내부 프로젝트 상세(P-02). 그 달의 프로젝트 사용량, 서비스별 사용량, 귀속된 구독료를 읽는다.

사용액과 상태는 표(project_budgets)와 같은 규칙이다: API 확정 + 추정 + 귀속 구독료.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, Budget, Project, Service, SubscriptionCost
from app.schemas.project_detail import (
    ProjectBudgetUsage,
    ProjectServiceUsage,
    ProjectSubscription,
    ProjectUsageDetail,
)
from app.services.budget_policy import evaluate_budget, share_of_budget
from app.services.internal_usage import api_conditions, cost_measures
from app.services.project_budgets import budget_conditions, month_period


def _usage_measures() -> list[Any]:
    """작업 수, 호출 수, 확정 합계, 추정 합계, 미확인 건수."""
    return [
        func.count(AIRequest.task_id.distinct()),
        func.count(),
        *cost_measures(),
    ]


def _budget_usage(
    month: date,
    budget: Budget | None,
    confirmed: Decimal,
    estimated: Decimal,
    subscription: Decimal,
    unknown_count: int,
) -> ProjectBudgetUsage:
    amount = budget.monthly_amount_usd if budget is not None else None
    # 구독료는 청구액이 정해진 금액이라 확정 쪽에 더한다
    evaluation = evaluate_budget(amount, confirmed + subscription, estimated)
    return ProjectBudgetUsage(
        month=month,
        monthly_amount_usd=amount,
        effective_from_month=budget.effective_from_month if budget else None,
        used_usd=evaluation.used_usd,
        usage_pct=evaluation.usage_pct,
        confirmed_usage_pct=evaluation.confirmed_usage_pct,
        remaining_usd=evaluation.remaining_usd,
        unknown_cost_count=unknown_count,
        status=evaluation.status,
    )


async def project_detail(
    session: AsyncSession, project_id: int, month: date
) -> ProjectUsageDetail | None:
    """그 달의 프로젝트 상세. 프로젝트가 없으면 None."""
    name = await session.scalar(
        select(Project.name).where(Project.project_id == project_id)
    )
    if name is None:
        return None
    conditions = [
        *api_conditions(month_period(month)),
        AIRequest.project_id == project_id,
    ]
    tasks, calls, confirmed, estimated, unknown_count = (
        await session.execute(select(*_usage_measures()).where(*conditions))
    ).one()
    service_rows = await session.execute(
        select(AIRequest.service_id, Service.name, *_usage_measures())
        .join(Service, Service.service_id == AIRequest.service_id)
        .where(*conditions)
        .group_by(AIRequest.service_id, Service.name)
    )
    subscription_rows = list(
        await session.scalars(
            select(SubscriptionCost)
            .where(
                SubscriptionCost.project_id == project_id,
                SubscriptionCost.applied_month == month.replace(day=1),
            )
            .order_by(SubscriptionCost.subscription_id)
        )
    )
    budget = await session.scalar(
        select(Budget).where(*budget_conditions(month), Budget.project_id == project_id)
    )
    subscription_total = sum((row.amount for row in subscription_rows), Decimal(0))
    budget_usage = _budget_usage(
        month, budget, confirmed, estimated, subscription_total, unknown_count
    )
    # 이름순. 같은 이름이면 ID순이다
    services = sorted(service_rows, key=lambda row: (row[1], row[0]))
    return ProjectUsageDetail(
        project_id=project_id,
        project_name=name,
        month=month,
        task_count=tasks,
        call_count=calls,
        confirmed_cost_usd=confirmed,
        estimated_cost_usd=estimated,
        subscription_usd=subscription_total,
        unknown_cost_count=unknown_count,
        budget=budget_usage,
        services=[
            ProjectServiceUsage(
                service_id=service_id,
                service_name=service_name,
                task_count=service_tasks,
                call_count=service_calls,
                confirmed_cost_usd=service_confirmed,
                estimated_cost_usd=service_estimated,
                unknown_cost_count=service_unknown,
                budget_share_pct=share_of_budget(
                    service_confirmed + service_estimated,
                    budget_usage.monthly_amount_usd,
                ),
            )
            for (
                service_id,
                service_name,
                service_tasks,
                service_calls,
                service_confirmed,
                service_estimated,
                service_unknown,
            ) in services
        ],
        subscriptions=[
            ProjectSubscription(
                subscription_id=row.subscription_id,
                tool_name=row.tool_name,
                amount_usd=row.amount,
                status=row.status,
            )
            for row in subscription_rows
        ],
    )

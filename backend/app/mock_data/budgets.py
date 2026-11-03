"""월 예산(고객·프로젝트)과 도구 구독료.

예산 금액은 생성된 사용량에 맞춰 10월에 상태가 고루 보이게 정했다. 로웰린 스튜디오 초과,
뮤렌 코스메틱 경고, 에이븐전자몰·솔레담 푸드 정상, 모뉴하우스 미설정. 초과한 고객은 11월부터
예산을 올렸다. 프로젝트 예산은 화면처럼 구독료를 포함한 사용액 기준이다(AI PDP 고도화 개발은
9월까지 주의, 10월부터 예산을 올려 정상). 금액은 테스트가 앱의 예산 판단 함수로 다시 확인한다.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.mock_data.organizations import project_id
from app.mock_data.rows import Row
from app.models import BudgetScopeType, SubscriptionStatus
from app.services.simulation_lookup import SIMULATOR_PROJECT_CODE

# 앱은 경고 기준을 80%로 고정해 쓰고 이 칸은 읽지 않는다. 화면 입력값과 같게 남긴다.
WARNING_THRESHOLD_PCT = Decimal(80)
AUGUST, SEPTEMBER, OCTOBER, NOVEMBER = (
    date(2026, month, 1) for month in (8, 9, 10, 11)
)
CUSTOMER, PROJECT = BudgetScopeType.CUSTOMER, BudgetScopeType.PROJECT


@dataclass(frozen=True)
class MockBudget:
    budget_id: int
    scope_type: BudgetScopeType
    owner_id: int  # 고객 또는 프로젝트 ID
    monthly_amount_usd: Decimal
    effective_from_month: date
    effective_to_month: date | None  # 종료 월 포함. None = 무기한
    created_by: int


BUDGETS = (
    MockBudget(1, CUSTOMER, 1, Decimal("3.80"), AUGUST, OCTOBER, 1),
    MockBudget(2, CUSTOMER, 1, Decimal("4.50"), NOVEMBER, None, 1),
    MockBudget(3, CUSTOMER, 2, Decimal("0.50"), AUGUST, None, 1),
    MockBudget(4, CUSTOMER, 3, Decimal("2.70"), SEPTEMBER, None, 2),
    MockBudget(5, CUSTOMER, 4, Decimal("0.12"), AUGUST, None, 2),
    MockBudget(6, CUSTOMER, 6, Decimal("1.50"), AUGUST, SEPTEMBER, 1),
    MockBudget(
        7, PROJECT, project_id("PRJ-PDP-DEV"), Decimal("36.00"), AUGUST, SEPTEMBER, 2
    ),
    MockBudget(
        8, PROJECT, project_id("PRJ-PDP-DEV"), Decimal("42.00"), OCTOBER, None, 2
    ),
    MockBudget(
        9, PROJECT, project_id(SIMULATOR_PROJECT_CODE), Decimal("0.50"), AUGUST, None, 1
    ),
)


def monthly_amount(
    scope_type: BudgetScopeType, owner_id: int, month: date
) -> Decimal | None:
    for budget in BUDGETS:
        if (budget.scope_type, budget.owner_id) != (scope_type, owner_id):
            continue
        if budget.effective_from_month <= month and (
            budget.effective_to_month is None or month <= budget.effective_to_month
        ):
            return budget.monthly_amount_usd
    return None


def budget_rows() -> list[Row]:
    return [
        {
            "budget_id": b.budget_id,
            "scope_type": b.scope_type,
            "customer_id": b.owner_id if b.scope_type == CUSTOMER else None,
            "project_id": b.owner_id if b.scope_type == PROJECT else None,
            "monthly_amount_usd": b.monthly_amount_usd,
            "warning_threshold_pct": WARNING_THRESHOLD_PCT,
            "effective_from_month": b.effective_from_month,
            "effective_to_month": b.effective_to_month,
            "created_by": b.created_by,
            "updated_by": b.created_by,
        }
        for b in BUDGETS
    ]


@dataclass(frozen=True)
class _Subscription:
    reference: str
    tool_name: str
    subscription_type: str
    amount: Decimal
    project_code: str | None  # None = 여러 프로젝트가 함께 써서 미배분
    months: tuple[date, ...]
    cancelled_in: date | None = None  # 해지를 신청한 달
    note: str | None = None


SUBSCRIPTIONS = (
    _Subscription("chatgpt-team-seat-01", "ChatGPT", "Team", Decimal(30), "PRJ-PDP-DEV",
                  (AUGUST, SEPTEMBER, OCTOBER), OCTOBER, "10월 말 해지, 11월부터 Claude 좌석으로 통합"),
    _Subscription("claude-team-seat-01", "Claude", "Team", Decimal(30), "PRJ-CUST-RENEWAL",
                  (AUGUST, SEPTEMBER, OCTOBER, NOVEMBER)),
    _Subscription("claude-team-seat-02", "Claude", "Team", Decimal(30), "PRJ-PDP-DEV", (NOVEMBER,)),
    _Subscription("cursor-pro-shared", "Cursor", "Pro", Decimal(20), None,
                  (AUGUST, SEPTEMBER, OCTOBER, NOVEMBER), note="여러 프로젝트가 함께 사용해 미배분"),
)  # fmt: skip


def subscription_rows() -> list[Row]:
    rows: list[Row] = []
    for item in SUBSCRIPTIONS:
        for month in item.months:
            cancelled = item.cancelled_in == month
            rows.append(
                {
                    "subscription_id": len(rows) + 1,
                    "subscription_reference": item.reference,
                    "tool_name": item.tool_name,
                    "subscription_type": item.subscription_type,
                    "applied_month": month,
                    "amount": item.amount,
                    "currency": "USD",
                    "project_id": project_id(item.project_code)
                    if item.project_code
                    else None,
                    "status": SubscriptionStatus.CANCELLED
                    if cancelled
                    else SubscriptionStatus.ACTIVE,
                    "note": item.note
                    if cancelled or item.project_code is None
                    else None,
                    "created_by": 1,
                    "updated_by": 1,
                }
            )
    return rows

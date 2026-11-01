"""내부 프로젝트 상세(P-02) 요청·응답 모델. 고객 상세(P-01)와 같은 모양에 구독료를 더했다.

금액은 문자열로 내려간다. 예산이 없으면 null이고, 0이 아니다.
"""

from pydantic import BaseModel, ConfigDict

from app.models import SubscriptionStatus
from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import Month
from app.services.budget_policy import BudgetStatus


class ProjectMonthQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: Month


class ProjectBudgetUsage(BaseModel):
    """그 달의 프로젝트 예산 현황. 사용액에는 이 프로젝트에 귀속된 구독료가 들어간다."""

    month: Month
    monthly_amount_usd: PlainDecimal | None  # 예산이 없으면 null
    effective_from_month: Month | None
    used_usd: PlainDecimal  # API 확정 + 추정 + 귀속 구독료
    usage_pct: PlainDecimal | None  # 추정 포함. 상태는 이 값으로 판단한다
    confirmed_usage_pct: PlainDecimal | None
    remaining_usd: PlainDecimal | None
    unknown_cost_count: int  # 사용액에 반영되지 않은 호출 수
    status: BudgetStatus


class ProjectServiceUsage(BaseModel):
    """서비스별 사용량. 서비스별 예산이 아니라 프로젝트 예산에서 차지하는 비중이다."""

    service_id: int
    service_name: str
    task_count: int
    call_count: int
    confirmed_cost_usd: PlainDecimal
    estimated_cost_usd: PlainDecimal
    unknown_cost_count: int
    budget_share_pct: PlainDecimal | None  # 예산이 없으면 null


class ProjectSubscription(BaseModel):
    subscription_id: int
    tool_name: str
    amount_usd: PlainDecimal
    status: SubscriptionStatus


class ProjectUsageDetail(BaseModel):
    project_id: int
    project_name: str
    month: Month
    task_count: int
    call_count: int
    confirmed_cost_usd: PlainDecimal
    estimated_cost_usd: PlainDecimal
    subscription_usd: PlainDecimal  # 해지(CANCELLED)된 구독료도 합계에 들어간다. 목록의 status로 구분한다
    unknown_cost_count: int
    budget: ProjectBudgetUsage
    services: list[ProjectServiceUsage]
    subscriptions: list[ProjectSubscription]

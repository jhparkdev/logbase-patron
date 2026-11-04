"""읽기 전용 사용량 도구 입력. 실제 조회 제약과 값은 기존 화면 계약을 재사용한다."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.internal_usage import InternalUsageQuery
from app.schemas.models import SortOrder
from app.schemas.usage import UsageFilterQuery
from app.services.budget_policy import BudgetStatus

TOOL_PAGE_SIZE = 5


class UsageToolOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: Literal["screen", "options", "summary", "requests", "budgets", "trend"] = (
        "screen"
    )
    period: Literal["screen", "today", "this_month", "last_month", "last_30_days"] = (
        "screen"
    )
    page: int = Field(default=1, ge=1, le=100)
    sort: Literal["recent", "cost", "tokens", "usage", "status"] = "recent"
    order: SortOrder = SortOrder.DESC
    model_name: str | None = Field(default=None, min_length=1, max_length=100)
    budget_status: BudgetStatus | None = None


class CustomerUsageToolQuery(UsageFilterQuery, UsageToolOptions):
    customer_name: str | None = Field(default=None, min_length=1, max_length=100)
    service_name: str | None = Field(default=None, min_length=1, max_length=100)


class InternalUsageToolQuery(InternalUsageQuery, UsageToolOptions):
    project_name: str | None = Field(default=None, min_length=1, max_length=100)

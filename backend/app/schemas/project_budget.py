"""내부 프로젝트 예산 현황(P-02) 요청·응답 모델. 금액은 문자열, 예산이 없으면 null이다."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.models import MAX_PAGE, SortOrder
from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import Month
from app.services.budget_policy import BudgetStatus

# 전체보기 한 페이지 개수. 기본값은 화면의 PAGE_SIZE와 같다
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


class ProjectRowSort(StrEnum):
    """프로젝트 표를 정렬할 수 있는 값. 이름은 화면 URL의 정렬 값과 같다."""

    PROJECT = "project"
    BUDGET = "budget"
    USED = "used"
    USAGE = "usage"
    STATUS = "status"


class ProjectRowsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 예산은 월 단위라 이 달의 예산과 사용액을 비교한다. 형식은 YYYY-MM이다
    month: Month
    # 예산을 넘었거나 넘을 것 같은 프로젝트가 위에 오도록 기본은 사용률이다
    sort: ProjectRowSort = ProjectRowSort.USAGE
    order: SortOrder = SortOrder.DESC
    # 요약 화면용 미리보기. 사용률이 높은 N개를 고른 뒤 그 안에서만 정렬하고 페이지는 나누지 않는다
    preview: bool = False
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class ProjectBudgetRow(BaseModel):
    project_id: int
    project_name: str
    monthly_amount_usd: PlainDecimal | None  # 그 달에 적용되는 예산이 없으면 null
    # API 확정 + 추정 + 이 프로젝트에 귀속된 구독료. 미확인 호출은 금액을 모르므로 넣지 않는다
    used_usd: PlainDecimal
    usage_pct: PlainDecimal | None  # 예산이 없으면 null(0%가 아니다)
    status: BudgetStatus
    unknown_cost_count: int  # 사용액에 반영되지 않은 호출 수


class ProjectBudgetPage(BaseModel):
    items: list[ProjectBudgetRow]
    total: int  # 전체 프로젝트 수. 미리보기여도 전체 기준이다
    page: int
    page_size: int

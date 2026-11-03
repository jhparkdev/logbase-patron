"""고객 AI 사용 현황(P-01) 요청·응답 모델. 금액은 문자열, 미확인 비용은 null로 내려간다."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)

from app.models import CostStatus, ErrorType, RequestStatus
from app.schemas.models import MAX_MODEL_ID, MAX_PAGE, SortOrder
from app.services.budget_policy import BudgetStatus

# 전체보기 한 페이지 개수. 기본값은 화면의 PAGE_SIZE와 같다
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
# 이전 기간과 다음 날을 계산해도 달력 범위를 벗어나지 않게 하는 조회 가능 범위
MIN_QUERY_DATE = date(2000, 1, 1)
MAX_QUERY_DATE = date(2100, 12, 31)
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
# budgets.monthly_amount_usd NUMERIC(30,18)에 들어가는 범위
AMOUNT_MAX_DECIMAL_PLACES = 18
AMOUNT_LIMIT = Decimal(10**12)

RowId = Annotated[int, Field(ge=1, le=MAX_MODEL_ID)]
QueryDate = Annotated[date, Field(ge=MIN_QUERY_DATE, le=MAX_QUERY_DATE)]


def _parse_month(value: object) -> date:
    """ "YYYY-MM"을 그 달 1일로 바꾼다. 서비스 안쪽에서 만든 date는 그대로 받는다."""
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or re.fullmatch(MONTH_PATTERN, value) is None:
        raise ValueError("월은 YYYY-MM 형식이어야 한다")
    month = date.fromisoformat(f"{value}-01")
    if not MIN_QUERY_DATE <= month <= MAX_QUERY_DATE:
        raise ValueError("조회할 수 없는 월이다")
    return month


def _require_decimal_string(value: object) -> object:
    """금액은 문자열로만 받는다. JSON 숫자는 float을 거치며 값이 달라질 수 있다."""
    if isinstance(value, str | Decimal):
        return value
    raise ValueError("금액은 문자열이어야 한다")


Month = Annotated[
    date,
    BeforeValidator(_parse_month),
    PlainSerializer(lambda value: value.strftime("%Y-%m"), return_type=str),
    WithJsonSchema({"type": "string", "pattern": MONTH_PATTERN}),
]


class CustomerRowSort(StrEnum):
    """고객 표를 정렬할 수 있는 값. 이름은 화면 URL의 정렬 값과 같다."""

    CUSTOMER = "customer"
    SERVICE = "service"
    TASKS = "tasks"
    CALLS = "calls"
    CONFIRMED = "confirmed"
    ESTIMATED = "estimated"
    BUDGET = "budget"
    USAGE = "usage"
    STATUS = "status"


class RequestRowSort(StrEnum):
    """호출 표를 정렬할 수 있는 값. 이름은 화면 URL의 정렬 값과 같다."""

    REQUESTED_AT = "requestedAt"
    CUSTOMER = "customer"
    SERVICE = "service"
    MODEL = "model"
    TASK_TYPE = "taskType"
    TOKENS = "tokens"
    COST = "cost"
    COST_STATUS = "costStatus"
    STATUS = "status"


class UsageFilterQuery(BaseModel):
    """요약·추이·표가 함께 쓰는 조회 조건. 기간 규칙은 오늘 날짜가 필요해 서비스가 판단한다."""

    model_config = ConfigDict(extra="forbid")

    start_date: QueryDate | None = None  # KST 달력 기준, 포함
    end_date: QueryDate | None = None  # KST 달력 기준, 포함
    customer_id: RowId | None = None
    service_id: RowId | None = None
    model_id: RowId | None = None


class _RowsQuery(UsageFilterQuery):
    order: SortOrder = SortOrder.DESC
    # 요약 화면용 미리보기. 정해진 N건을 고른 뒤 그 안에서만 정렬하고 페이지는 나누지 않는다
    preview: bool = False
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class CustomerRowsQuery(_RowsQuery):
    sort: CustomerRowSort = CustomerRowSort.CONFIRMED


class RequestRowsQuery(_RowsQuery):
    sort: RequestRowSort = RequestRowSort.REQUESTED_AT


class CustomerMonthQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: Month


class UsageOption(BaseModel):
    id: int
    name: str


class UsageOptions(BaseModel):
    """선택 상자 목록. 서비스는 고객용만, 모델은 고객 호출에 쓰인 것만 준다."""

    customers: list[UsageOption]
    services: list[UsageOption]
    models: list[UsageOption]


class UsageSummary(BaseModel):
    """요약 카드. *_change_pct는 직전 동일 길이 기간 대비 증감률이고 비교할 값이 0이면 null이다."""

    comparison_start_date: date
    comparison_end_date: date
    task_count: int
    call_count: int
    success_count: int
    failed_count: int
    timeout_count: int
    input_tokens: int
    output_tokens: int
    confirmed_cost_usd: Decimal
    estimated_cost_usd: Decimal
    unknown_cost_count: int
    task_change_pct: Decimal | None
    call_change_pct: Decimal | None
    confirmed_cost_change_pct: Decimal | None
    estimated_cost_change_pct: Decimal | None


class UsageTrendPoint(BaseModel):
    date: date
    task_count: int
    call_count: int
    confirmed_cost_usd: Decimal
    estimated_cost_usd: Decimal
    unknown_cost_count: int


class UsageTrend(BaseModel):
    """조회 기간의 모든 KST 날짜. 호출이 없는 날도 0으로 채운다."""

    items: list[UsageTrendPoint]


class BudgetUsage(BaseModel):
    """그 달의 고객 예산 현황. 서비스·모델 필터와 관계없이 고객 전체 사용액으로 계산한다."""

    month: Month
    monthly_amount_usd: Decimal | None  # 예산이 없으면 null
    effective_from_month: Month | None
    used_usd: Decimal  # 확정 + 추정
    usage_pct: Decimal | None  # 추정 포함. 상태는 이 값으로 판단한다
    confirmed_usage_pct: Decimal | None
    remaining_usd: Decimal | None
    unknown_cost_count: int  # 사용액에 반영되지 않은 호출 수
    status: BudgetStatus
    warning_threshold_pct: Decimal  # 상태 판단에 쓰는 WARNING 기준 사용률


class CustomerUsageRow(BaseModel):
    """고객 × 서비스 한 행. 고객을 알 수 없는 호출은 customer_id가 null인 미분류 행으로 모은다."""

    customer_id: int | None
    customer_name: str | None
    service_id: int
    service_name: str
    task_count: int
    call_count: int
    confirmed_cost_usd: Decimal
    estimated_cost_usd: Decimal
    unknown_cost_count: int
    budget: BudgetUsage


class CustomerUsagePage(BaseModel):
    items: list[CustomerUsageRow]
    total: int  # 조건에 맞는 전체 행 수. 미리보기여도 전체 기준이다
    page: int
    page_size: int


class CustomerRequestRow(BaseModel):
    request_id: UUID
    requested_at: datetime
    customer_id: int | None
    customer_name: str | None
    service_id: int
    service_name: str
    model: str  # 실제 호출된 모델. 없으면 요청한 모델
    task_id: UUID | None
    task_type: str | None
    task_type_label: str | None  # 화면에 보여 줄 이름. 작업이 없으면 null
    tokens: int | None  # 입력 + 출력. 어느 쪽이든 모르면 null
    cost_usd: Decimal | None
    cost_status: CostStatus
    status: RequestStatus
    error_type: ErrorType | None


class CustomerRequestPage(BaseModel):
    items: list[CustomerRequestRow]
    total: int  # 조건에 맞는 전체 호출 수. 미리보기여도 전체 기준이다
    page: int
    page_size: int


class CustomerServiceUsage(BaseModel):
    """고객 상세의 서비스별 사용량. 서비스별 예산이 아니라 고객 예산에서 차지하는 비중이다."""

    service_id: int
    service_name: str
    task_count: int
    call_count: int
    confirmed_cost_usd: Decimal
    estimated_cost_usd: Decimal
    total_cost_usd: Decimal  # 확정 + 추정. 미확인은 금액을 모르므로 건수로만 센다
    unknown_cost_count: int
    budget_share_pct: Decimal | None  # 예산이 없으면 null


class CustomerUsageDetail(BaseModel):
    """고객 상세 패널. 그 달의 고객 전체 서비스 합계다."""

    customer_id: int
    customer_name: str
    month: Month
    task_count: int
    call_count: int
    confirmed_cost_usd: Decimal
    estimated_cost_usd: Decimal
    unknown_cost_count: int
    budget: BudgetUsage
    services: list[CustomerServiceUsage]


class CustomerBudgetSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_amount_usd: Annotated[
        Decimal,
        BeforeValidator(_require_decimal_string),
        Field(gt=0, lt=AMOUNT_LIMIT, decimal_places=AMOUNT_MAX_DECIMAL_PLACES),
    ]
    effective_from_month: Month


class CustomerBudgetRead(BaseModel):
    budget_id: int
    customer_id: int
    monthly_amount_usd: Decimal
    effective_from_month: Month
    effective_to_month: Month | None

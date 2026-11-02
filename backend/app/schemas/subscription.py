"""월 구독료(P-02) 요청·응답 모델. 금액은 문자열이고, 프로젝트가 없는 구독료(미배분)는 project_id가 null이다."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import SubscriptionStatus
from app.schemas.decimal_string import require_decimal_string
from app.schemas.internal_usage import InternalFilterQuery
from app.schemas.models import MAX_MODEL_ID, MAX_PAGE, SortOrder
from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Month

# subscription_costs.amount NUMERIC(14,4)에 들어가는 범위
AMOUNT_MAX_DECIMAL_PLACES = 4
AMOUNT_LIMIT = Decimal(10**10)
NOTE_MAX_LENGTH = 500
SHORT_TEXT_MAX_LENGTH = 100
# 비워 두면 안 되는 항목. null을 보내면 값이 지워지는 항목(project_id, note)과 구분한다
REQUIRED_FIELDS = ("amount_usd", "status")

SubscriptionAmount = Annotated[
    Decimal,
    BeforeValidator(require_decimal_string),
    Field(ge=0, lt=AMOUNT_LIMIT, decimal_places=AMOUNT_MAX_DECIMAL_PLACES),
]
ProjectId = Annotated[int, Field(ge=1, le=MAX_MODEL_ID)]
Note = Annotated[str, Field(max_length=NOTE_MAX_LENGTH)]
# 식별값, 도구 이름, 종류. 앞뒤 공백을 지우고 빈 값은 받지 않는다
ShortText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH
    ),
]


class SubscriptionSort(StrEnum):
    """구독료 표를 정렬할 수 있는 값. 이름은 화면 URL의 정렬 값과 같다."""

    TOOL = "tool"
    MONTH = "month"
    AMOUNT = "amount"
    PROJECT = "project"
    STATUS = "status"


class SubscriptionsQuery(InternalFilterQuery):
    """기간은 요약·추이와 같은 규칙이다. 기간을 보내지 않으면 최근 30일이 걸치는 달이다."""

    # 고르면 그 프로젝트에 배분한 구독료만 나온다. 배분하지 않은 구독료는 빠진다
    project_id: ProjectId | None = None
    sort: SubscriptionSort = SubscriptionSort.MONTH
    order: SortOrder = SortOrder.DESC
    # 요약 화면용 미리보기. 적용 월이 최근인 N건을 고른 뒤 그 안에서만 정렬하고 페이지는 나누지 않는다
    preview: bool = False
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class SubscriptionRow(BaseModel):
    subscription_id: int
    # 구독 하나를 구분하는 값. 같은 구독은 매달 같은 값을 쓴다
    subscription_reference: str
    tool_name: str
    subscription_type: str | None
    applied_month: Month
    amount_usd: PlainDecimal
    project_id: int | None  # 프로젝트에 배분하지 않았으면 null
    project_name: str | None
    status: SubscriptionStatus
    note: str | None


class SubscriptionList(BaseModel):
    items: list[SubscriptionRow]
    total: int  # 조회 기간의 전체 구독료 수. 미리보기여도 전체 기준이다
    page: int
    page_size: int


class SubscriptionProject(BaseModel):
    project_id: int
    name: str


class SubscriptionOptions(BaseModel):
    projects: list[SubscriptionProject]


class SubscriptionCreate(BaseModel):
    """구독료 등록. 같은 subscription_reference와 applied_month는 한 번만 등록할 수 있다."""

    model_config = ConfigDict(extra="forbid")

    subscription_reference: ShortText
    tool_name: ShortText
    subscription_type: ShortText | None = None
    applied_month: Month
    amount_usd: SubscriptionAmount
    project_id: ProjectId | None = None  # 없으면 미배분
    note: Note | None = None


class SubscriptionUpdate(BaseModel):
    """보낸 항목만 바꾼다. project_id와 note는 null을 보내면 값이 지워진다."""

    model_config = ConfigDict(extra="forbid")

    amount_usd: SubscriptionAmount | None = None
    project_id: ProjectId | None = None
    status: SubscriptionStatus | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("수정할 항목을 하나 이상 보내야 한다")
        for name in REQUIRED_FIELDS:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name}은 비울 수 없다")
        return self

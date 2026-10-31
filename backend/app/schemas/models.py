"""모델 관리(P-03) 요청·응답 모델."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models import ConnectionTestStatus, ModelStatus, PriceSource, PriceStatus

# 한 페이지 개수의 기본값과 최댓값, 검색어 최대 길이
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_FILTER_LENGTH = 100


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class ModelSortField(StrEnum):
    """목록을 정렬할 수 있는 값. 이 밖의 값은 거절한다."""

    DISPLAY_NAME = "display_name"
    OPENROUTER_MODEL_ID = "openrouter_model_id"
    PROVIDER = "provider"
    INPUT_MODALITIES = "input_modalities"
    PRICE_INPUT = "price_input"
    PRICE_OUTPUT = "price_output"
    STATUS = "status"
    LAST_TEST_AT = "last_test_at"
    LAST_TEST_STATUS = "last_test_status"
    PURPOSE = "purpose"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class ModelListQuery(BaseModel):
    """GET /api/models의 검색 조건. 정해지지 않은 조건 이름은 거절한다."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=MAX_FILTER_LENGTH)
    model_id: str | None = Field(
        default=None, min_length=1, max_length=MAX_FILTER_LENGTH
    )
    provider: str | None = Field(
        default=None, min_length=1, max_length=MAX_FILTER_LENGTH
    )
    status: list[ModelStatus] = Field(default_factory=list)
    sort: ModelSortField = ModelSortField.CREATED_AT
    order: SortOrder = SortOrder.DESC
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class PriceRead(BaseModel):
    """토큰 1개당 단가(USD). 금액은 문자열로 내려간다."""

    model_config = ConfigDict(from_attributes=True)

    price_id: int
    execution_provider: str | None
    currency: str
    price_status: PriceStatus
    input_price_per_token: Decimal | None
    output_price_per_token: Decimal | None
    cache_read_price_per_token: Decimal | None
    cache_write_price_per_token: Decimal | None
    source: PriceSource
    effective_from: datetime
    effective_to: datetime | None
    checked_at: datetime


class ModelRead(BaseModel):
    model_id: int
    openrouter_model_id: str
    display_name: str
    # 모델 제공사(예: mistralai). 호출을 처리한 업체가 아니다.
    provider: str
    purpose: str | None
    status: ModelStatus
    input_modalities: list[str]
    output_modalities: list[str]
    supports_json_schema: bool
    context_length: int | None
    # 가격이 없으면 null("가격 미확인")
    current_price: PriceRead | None
    last_test_status: ConnectionTestStatus | None
    last_test_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ModelListResponse(BaseModel):
    items: list[ModelRead]
    page: int
    page_size: int
    total: int

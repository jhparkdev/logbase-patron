"""내부 호출 이력(P-02) 요청·응답 모델. 금액은 문자열이고 비용을 모르면 null이다(0이 아니다)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import CostStatus, ErrorType, RequestStatus, UsageOrigin
from app.schemas.internal_usage import InternalFilterQuery
from app.schemas.models import MAX_PAGE, SortOrder
from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, RowId, UsageOption


class InternalRequestSort(StrEnum):
    """호출 표를 정렬할 수 있는 값. 이름은 화면 URL의 정렬 값과 같다."""

    REQUESTED_AT = "requestedAt"
    PROJECT = "project"
    SERVICE = "service"
    MODEL = "model"
    TASK_TYPE = "taskType"
    TOKENS = "tokens"
    COST = "cost"
    COST_STATUS = "costStatus"
    STATUS = "status"
    # 호출 출처(내부 개발, 시뮬레이션, 시스템 테스트)
    ORIGIN = "origin"


class InternalRequestsQuery(InternalFilterQuery):
    """기간은 요약·추이와 같은 규칙이다. 기간을 보내지 않으면 최근 30일이다."""

    project_id: RowId | None = None
    service_id: RowId | None = None
    model_id: RowId | None = None
    sort: InternalRequestSort = InternalRequestSort.REQUESTED_AT
    order: SortOrder = SortOrder.DESC
    # 요약 화면용 미리보기. 최근 N건을 고른 뒤 그 안에서만 정렬하고 페이지는 나누지 않는다
    preview: bool = False
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class InternalRequestRow(BaseModel):
    request_id: UUID
    requested_at: datetime
    usage_origin: UsageOrigin  # 개발, 시뮬레이션, 시스템 테스트 중 하나
    project_id: int | None
    project_name: str | None
    service_id: int
    service_name: str
    model: str  # 실제 호출된 모델. 없으면 요청한 모델
    task_id: UUID | None
    task_type: str | None
    task_type_label: str | None  # 화면에 보여 줄 이름. 작업이 없으면 null
    tokens: int | None  # 입력 + 출력. 어느 쪽이든 모르면 null
    cost_usd: PlainDecimal | None  # 비용을 모르면 null
    cost_status: CostStatus
    status: RequestStatus
    error_type: ErrorType | None


class InternalRequestPage(BaseModel):
    items: list[InternalRequestRow]
    total: int  # 조건에 맞는 전체 호출 수. 미리보기여도 전체 기준이다
    page: int
    page_size: int


class InternalOptions(BaseModel):
    """선택 상자 목록. 프로젝트는 사용 중인 것, 서비스와 모델은 내부 호출에 쓰인 것만 준다."""

    projects: list[UsageOption]
    services: list[UsageOption]
    models: list[UsageOption]

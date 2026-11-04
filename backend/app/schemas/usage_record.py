"""고객 서비스 호출 기록 수신(POST /api/usage-records)의 요청·응답 모델. 연동 규격의 정본이다.

고객 서비스가 OpenRouter 호출을 마칠 때마다 한 건씩 보낸다. 프롬프트와 답변은 받지 않는다
(알 수 없는 필드는 거절한다). Key 원문도 받지 않고 Patron이 정한 key_id만 받는다.
"""

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import ErrorType

MAX_TEXT_LENGTH = 200
MIN_HTTP_STATUS = 100
MAX_HTTP_STATUS = 599

Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_LENGTH),
]
Count = Annotated[int, Field(ge=0)]


class UsageRecordStatus(StrEnum):
    """호출의 최종 결과. 진행 중이거나 취소된 호출은 보내지 않는다."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class UsageRecordCreate(BaseModel):
    """호출 한 건의 기록. 같은 request_id 로 다시 보내도 한 번만 저장된다."""

    model_config = ConfigDict(extra="forbid")

    # 고객 서비스가 호출마다 직접 만드는 UUID. timeout 처럼 OpenRouter 응답 id가 없는 호출도 이것으로 구분한다
    request_id: uuid.UUID
    # OpenRouter 응답 id. 응답을 받은 경우에만 보낸다
    openrouter_generation_id: Text | None = None
    # Key를 등록할 때 Patron이 알려 준 key_id. Key 원문은 보내지 않는다
    key_id: Annotated[int, Field(gt=0)]
    # 고객 코드. Key에 연결된 고객과 같아야 한다
    customer_code: Text
    # 고객이 돈을 내는 작업 한 건의 ID(예: 상세페이지 1건). 한 작업의 호출들을 묶는 기준이다
    task_ref: Text
    # 작업 종류(예: 상세페이지 생성)
    task_type: Text
    # 요청한 OpenRouter 모델 ID
    model: Text
    # 실제로 처리한 모델과 서버 업체. 응답을 받은 경우에만 보낸다
    actual_model: Text | None = None
    actual_provider: Text | None = None
    requested_at: AwareDatetime
    # timeout 처럼 끝난 시각을 모르면 보내지 않는다
    completed_at: AwareDatetime | None = None
    # 걸린 시간(밀리초). 없으면 requested_at 과 completed_at 의 차이로 계산한다
    latency_ms: Count | None = None
    status: UsageRecordStatus
    # FAILED 이면 필수. TIMEOUT 이면 없을 때 TIMEOUT_ERROR 로 저장한다. SUCCESS 이면 보낼 수 없다
    error_type: ErrorType | None = None
    http_status: (
        Annotated[int, Field(ge=MIN_HTTP_STATUS, le=MAX_HTTP_STATUS)] | None
    ) = None
    finish_reason: Text | None = None
    input_tokens: Count | None = None
    output_tokens: Count | None = None
    cached_tokens: Count | None = None
    reasoning_tokens: Count | None = None
    # OpenRouter 응답의 비용(USD). SUCCESS 일 때만 쓰고, 없으면 미확인으로 저장한다(0이 아니다)
    cost_usd: Annotated[Decimal, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def check_rules(self) -> Self:
        if self.completed_at is not None and self.completed_at < self.requested_at:
            raise ValueError("completed_at 은 requested_at 보다 빠를 수 없습니다")
        if self.status == UsageRecordStatus.SUCCESS and self.error_type is not None:
            raise ValueError("SUCCESS 기록에는 error_type 을 보낼 수 없습니다")
        if self.status == UsageRecordStatus.FAILED and self.error_type is None:
            raise ValueError("FAILED 기록에는 error_type 이 필요합니다")
        if self.status == UsageRecordStatus.TIMEOUT and self.error_type is None:
            self.error_type = ErrorType.TIMEOUT_ERROR
        if (
            self.cached_tokens is not None
            and self.input_tokens is not None
            and self.cached_tokens > self.input_tokens
        ):
            raise ValueError("cached_tokens 는 input_tokens 보다 클 수 없습니다")
        if (
            self.reasoning_tokens is not None
            and self.output_tokens is not None
            and self.reasoning_tokens > self.output_tokens
        ):
            raise ValueError("reasoning_tokens 는 output_tokens 보다 클 수 없습니다")
        return self


class UsageRecordReceipt(BaseModel):
    """받은 기록을 어떻게 처리했는지만 알린다. 기록 내용은 돌려주지 않는다."""

    request_id: uuid.UUID
    # False 이면 이미 저장된 요청이라 이번에는 저장하지 않았다
    stored: bool

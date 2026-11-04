"""시뮬레이터에서 호출 이력 저장에 전달하는 읽기 전용 필드.

NewRequest·SlotRecord와 같은 속성을 가진 객체를 받을 수 있게 구조로 정의한다.
원문은 save_payload에서 별도로 저장하고 JSON 검증 결과는 시뮬레이터가 저장한다.

Protocol은 객체를 만들거나 DB를 조회하는 구현이 아니라, 입력 객체에 필요한 속성의 규격이다.
속성이 맞으면 이 클래스를 상속하지 않아도 된다. 각 속성의 ...은 실행 코드가 빠진 것이 아니다.
@property는 읽기만 요구하므로, 수정할 수 없는 dataclass도 입력으로 사용할 수 있다.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pydantic import JsonValue

from app.models import (
    CallPurpose,
    CostStatus,
    DataSource,
    ErrorType,
    RequestStatus,
    UsageOrigin,
)


class PendingRequest(Protocol):
    """호출자가 정한 ID·귀속·실행 조건을 create_pending에 전달할 때의 규격."""

    @property
    def request_id(self) -> uuid.UUID: ...

    @property
    def simulation_id(self) -> uuid.UUID | None: ...

    @property
    def usage_origin(self) -> UsageOrigin: ...

    @property
    def call_purpose(self) -> CallPurpose: ...

    @property
    def attempt_no(self) -> int: ...

    @property
    def project_id(self) -> int: ...

    @property
    def key_id(self) -> int: ...

    @property
    def service_id(self) -> int: ...

    @property
    def executed_by(self) -> int | None: ...

    @property
    def model_id(self) -> int | None: ...

    @property
    def requested_model(self) -> str: ...

    @property
    def requested_provider(self) -> str: ...

    @property
    def routing_policy(self) -> Mapping[str, JsonValue]: ...

    @property
    def execution_config(self) -> Mapping[str, JsonValue]: ...

    @property
    def input_hash(self) -> str: ...

    @property
    def requested_at(self) -> datetime: ...

    @property
    def data_source(self) -> DataSource: ...


class RequestResult(Protocol):
    """상태·토큰·금액 등 종료 시 함께 저장할 값. 비용 근거는 함수 인자로 따로 받는다."""

    @property
    def status(self) -> RequestStatus: ...

    @property
    def error_type(self) -> ErrorType | None: ...

    @property
    def input_tokens(self) -> int | None: ...

    @property
    def output_tokens(self) -> int | None: ...

    @property
    def cost_usd(self) -> Decimal | None: ...

    @property
    def cost_status(self) -> CostStatus: ...

    @property
    def actual_provider(self) -> str | None: ...

    @property
    def actual_model(self) -> str | None: ...

    @property
    def latency_ms(self) -> int | None: ...

    @property
    def external_generation_id(self) -> str | None: ...


@dataclass(frozen=True)
class FinishedCall:
    """이미 끝난 외부 호출 한 건(고객 서비스의 OpenRouter 호출)을 기록할 때의 값.

    프롬프트·답변은 담지 않는다. 비용은 OpenRouter가 알려 준 값이 있을 때만 확정으로 기록하고,
    없으면 미확인(NULL)이다. 실패·timeout 호출의 비용은 항상 미확인이다.
    """

    request_id: uuid.UUID
    key_id: int
    # 고객을 알 수 없는 호출(프로젝트 Key로 들어온 고객 호출)은 None 이고 미분류로 집계된다
    customer_id: int | None
    service_id: int
    task_id: uuid.UUID
    model_id: int | None
    requested_model: str
    actual_model: str | None
    actual_provider: str | None
    finish_reason: str | None
    status: RequestStatus
    error_type: ErrorType | None
    http_status: int | None
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    reasoning_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int | None
    requested_at: datetime
    completed_at: datetime | None
    external_generation_id: str | None

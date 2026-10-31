"""시뮬레이터의 호출 생성 입력과 종료 결과를 흉내 내는 고정 테스트 데이터.

실제 시뮬레이터 코드가 없어도 같은 속성을 가진 객체로 저장 함수를 검증한다.
frozen으로 필드 재할당을 막고, 잘못된 입력은 dataclasses.replace로 일부 필드만 바꿔 만든다.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import JsonValue

from app.models import (
    CallPurpose,
    CostStatus,
    DataSource,
    ErrorType,
    RequestStatus,
    UsageOrigin,
)


@dataclass(frozen=True)
class PendingRecord:
    request_id: UUID
    simulation_id: UUID | None
    usage_origin: UsageOrigin
    call_purpose: CallPurpose
    attempt_no: int
    project_id: int
    key_id: int
    service_id: int
    executed_by: int | None
    model_id: int | None
    requested_model: str
    requested_provider: str
    routing_policy: dict[str, JsonValue]
    execution_config: dict[str, JsonValue]
    input_hash: str
    requested_at: datetime
    data_source: DataSource


@dataclass(frozen=True)
class FinishedRecord:
    status: RequestStatus = RequestStatus.SUCCESS
    error_type: ErrorType | None = None
    input_tokens: int | None = 20
    output_tokens: int | None = 10
    cost_usd: Decimal | None = Decimal("0.05")
    cost_status: CostStatus = CostStatus.CONFIRMED
    actual_provider: str | None = "actual-provider"
    actual_model: str | None = "vendor/actual-model"
    latency_ms: int | None = 42000
    external_generation_id: str | None = "gen-test-finished"

"""비교 실행이 기대하는 외부 모듈의 모양.

건호님 services/requests.py 와 정욱님 openrouter/client.py 가 합류하면 이 모양에 맞춰 연결한다.
아직 없는 동안에는 가짜 객체로 같은 모양을 흉내 내어 실행 흐름을 검증한다.
"""

import asyncio
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.models import (
    CostStatus,
    ErrorType,
    RequestStatus,
    SimulationStatus,
    ValidationStatus,
)
from app.services.simulation_json_check import ValidationErrors


@dataclass(frozen=True)
class ModelCallResult:
    """call_model 이 돌려주는 결과. 필드 이름은 정욱님의 CallResult 를 따른다."""

    status: RequestStatus
    content: str | None
    error_type: ErrorType | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: Decimal | None
    cost_status: CostStatus
    actual_model: str | None
    provider: str | None  # 실제 처리한 업체
    latency_ms: int | None
    generation_id: str | None


@dataclass(frozen=True)
class SlotRecord:
    """모델 한 칸의 호출 결과에서 저장할 값. ai_requests 와 simulation_results 에 나뉘어 들어간다."""

    status: RequestStatus
    error_type: ErrorType | None
    response_text: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None  # cost_status 가 UNKNOWN 이면 항상 None
    cost_status: CostStatus
    actual_provider: str | None
    actual_model: str | None
    latency_ms: int | None
    external_generation_id: str | None
    json_parse_status: ValidationStatus
    schema_validation_status: ValidationStatus
    missing_required_fields: list[str] | None
    validation_errors: ValidationErrors | None


@dataclass(frozen=True)
class SlotPlan:
    """저장이 끝난 모델 한 칸. 이 칸을 호출하면 된다."""

    slot_no: int
    request_id: uuid.UUID
    model_id: int
    openrouter_model_id: str
    execution_provider: str


@dataclass(frozen=True)
class SimulationJob:
    """실행할 비교 한 건. 모든 칸에 같은 입력을 보낸다."""

    simulation_id: uuid.UUID
    slots: Sequence[SlotPlan]
    messages: list[dict[str, str]]
    json_schema: dict[str, Any] | None
    execution_config: Mapping[str, Any]
    allow_fallbacks: bool


class ModelCaller(Protocol):
    """정욱님 call_model. 실패해도 예외를 던지지 않고 결과로 돌려준다."""

    async def __call__(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        provider_order: list[str],
        allow_fallbacks: bool,
        json_schema: dict[str, Any] | None,
        execution_config: Mapping[str, Any],
        timeout_seconds: float,
        cancel: asyncio.Event,
    ) -> ModelCallResult: ...


class RequestRecorder(Protocol):
    """건호님 services/requests.py 에서 필요한 것. 상태 변경은 모두 조건부이고 바뀌었는지를 돌려준다."""

    async def mark_running(self, request_id: uuid.UUID, now: datetime) -> bool:
        """PENDING 일 때만 RUNNING 으로 바꾼다. 이미 취소되었으면 False."""
        ...

    async def record_finished(
        self, request_id: uuid.UUID, record: SlotRecord, now: datetime
    ) -> bool:
        """RUNNING 일 때만 종료 상태·토큰·비용·실제 업체 등을 기록한다. 이미 종료되었으면 False."""
        ...

    async def save_payload(
        self,
        request_id: uuid.UUID,
        messages: list[dict[str, str]],
        response_text: str | None,
    ) -> None: ...


class SimulationStore(Protocol):
    """simulation_runs·simulation_results 접근. 우리 몫이다."""

    async def mark_started(self, simulation_id: uuid.UUID, now: datetime) -> None: ...

    async def touch_heartbeat(
        self, simulation_id: uuid.UUID, now: datetime
    ) -> None: ...

    async def save_validation(
        self, request_id: uuid.UUID, record: SlotRecord
    ) -> None: ...

    async def final_statuses(self, simulation_id: uuid.UUID) -> list[RequestStatus]:
        """칸마다 최종 시도의 상태."""
        ...

    async def mark_finished(
        self, simulation_id: uuid.UUID, status: SimulationStatus, now: datetime
    ) -> None: ...


@dataclass(frozen=True)
class SimulationDeps:
    caller: ModelCaller
    recorder: RequestRecorder
    store: SimulationStore
    now: Callable[[], datetime]  # 현재 시각은 주입한다

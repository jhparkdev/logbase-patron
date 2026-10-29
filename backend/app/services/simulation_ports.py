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
    CallPurpose,
    CostStatus,
    DataSource,
    ErrorType,
    ModelStatus,
    RequestStatus,
    SimulationStatus,
    TestType,
    UsageOrigin,
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


@dataclass(frozen=True)
class ScenarioInfo:
    """접수 때 읽는 시나리오. 기본 실행 설정과 기본 Schema 를 쓴다."""

    scenario_id: int
    is_active: bool
    default_json_schema: dict[str, Any] | None
    default_execution_config: Mapping[str, Any]


@dataclass(frozen=True)
class ModelInfo:
    """접수 때 읽는 모델. 이름과 상태는 실행 당시 값으로 결과에 복사해 둔다."""

    model_id: int
    openrouter_model_id: str
    display_name: str
    status: ModelStatus


@dataclass(frozen=True)
class SimulatorContext:
    """시뮬레이터 호출의 비용 귀속. 서버가 정하고 사용자는 보내지 않는다."""

    project_id: int
    key_id: int
    service_id: int


@dataclass(frozen=True)
class NewRun:
    """저장할 simulation_runs 한 행."""

    simulation_id: uuid.UUID
    rerun_of_simulation_id: uuid.UUID | None
    test_type: TestType
    scenario_id: int | None
    prompt_text: str
    input_text: str | None
    json_schema: dict[str, Any] | None
    execution_config: dict[str, Any]
    routing_policy: dict[str, Any]
    input_hash: str
    model_count: int
    project_id: int
    key_id: int
    executed_by: int
    requested_at: datetime
    data_source: DataSource


@dataclass(frozen=True)
class NewRequest:
    """저장할 ai_requests 한 행(PENDING). 만드는 곳은 건호님 services/requests.py 다."""

    request_id: uuid.UUID
    simulation_id: uuid.UUID
    usage_origin: UsageOrigin
    call_purpose: CallPurpose
    attempt_no: int
    project_id: int
    key_id: int
    service_id: int
    executed_by: int
    model_id: int
    requested_model: str  # OpenRouter 모델 ID
    requested_provider: str
    routing_policy: dict[str, Any]
    execution_config: dict[str, Any]
    input_hash: str
    requested_at: datetime
    data_source: DataSource


@dataclass(frozen=True)
class NewResult:
    """저장할 simulation_results 한 행. 칸 번호와 실행 당시의 모델 이름·상태를 남긴다."""

    simulation_id: uuid.UUID
    request_id: uuid.UUID
    slot_no: int
    model_id: int
    execution_provider: str
    model_status_at_run: ModelStatus
    model_display_name_at_run: str


@dataclass(frozen=True)
class SlotState:
    """칸 하나의 현재 상태. 칸마다 최종 시도만 다룬다."""

    request_id: uuid.UUID
    slot_no: int
    status: RequestStatus


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

    async def create_pending(self, request: NewRequest) -> None:
        """호출 이력을 PENDING 으로 만든다. 호출 전에 Request ID 를 저장해 두는 것이 원칙이다."""
        ...

    async def cancel_if_open(self, request_id: uuid.UUID, now: datetime) -> bool:
        """PENDING 이나 RUNNING 일 때만 CANCELLED 로 바꾼다. 이미 종료되었으면 False.

        취소와 정상 완료가 거의 동시에 올 때 어느 쪽이 이길지를 DB 의 조건부 갱신이 정한다.
        """
        ...

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

    async def insert_run(self, run: NewRun) -> None: ...

    async def insert_result(self, result: NewResult) -> None: ...

    async def mark_started(self, simulation_id: uuid.UUID, now: datetime) -> None: ...

    async def touch_heartbeat(
        self, simulation_id: uuid.UUID, now: datetime
    ) -> None: ...

    async def save_validation(
        self, request_id: uuid.UUID, record: SlotRecord
    ) -> None: ...

    async def list_slots(self, simulation_id: uuid.UUID) -> list[SlotState] | None:
        """칸 번호 순서로 칸마다 최종 시도의 상태. 없는 실행이면 None."""
        ...

    async def final_statuses(self, simulation_id: uuid.UUID) -> list[RequestStatus]:
        """칸마다 최종 시도의 상태."""
        ...

    async def mark_finished(
        self, simulation_id: uuid.UUID, status: SimulationStatus, now: datetime
    ) -> None: ...


class SimulationLookup(Protocol):
    """접수 때 DB 에서 읽는 것. 읽기만 한다."""

    async def find_scenario(self, scenario_id: int) -> ScenarioInfo | None: ...

    async def find_models(self, model_ids: Sequence[int]) -> dict[int, ModelInfo]: ...

    async def simulation_exists(self, simulation_id: uuid.UUID) -> bool: ...

    async def simulator_context(self) -> SimulatorContext: ...


@dataclass(frozen=True)
class IntakeDeps:
    """요청 접수에 필요한 것. 현재 시각과 새 ID 는 주입한다."""

    lookup: SimulationLookup
    recorder: RequestRecorder
    store: SimulationStore
    now: Callable[[], datetime]
    new_id: Callable[[], uuid.UUID]


@dataclass(frozen=True)
class SimulationDeps:
    caller: ModelCaller
    recorder: RequestRecorder
    store: SimulationStore
    now: Callable[[], datetime]  # 현재 시각은 주입한다

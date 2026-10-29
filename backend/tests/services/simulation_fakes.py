"""비교 실행 서비스 테스트용 가짜 객체. DB 와 OpenRouter 없이 동작을 검증한다."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models import CostStatus, ModelStatus, RequestStatus, SimulationStatus
from app.services.simulation_ports import (
    ModelCallResult,
    ModelInfo,
    NewRequest,
    NewResult,
    NewRun,
    ScenarioInfo,
    SimulationDeps,
    SimulationJob,
    SimulatorContext,
    SlotPlan,
    SlotRecord,
)

NOW = datetime(2026, 10, 29, 1, 0, tzinfo=UTC)

R = RequestStatus

CallBehavior = Callable[[dict[str, Any]], Awaitable[ModelCallResult]]


def ok(content: str = "응답") -> ModelCallResult:
    return ModelCallResult(
        status=R.SUCCESS,
        content=content,
        error_type=None,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=Decimal("0.001"),
        cost_status=CostStatus.CONFIRMED,
        actual_model="m",
        provider="P",
        latency_ms=100,
        generation_id="gen",
    )


def failed(status: RequestStatus = R.FAILED) -> ModelCallResult:
    return ModelCallResult(
        status=status,
        content=None,
        error_type=None,
        prompt_tokens=None,
        completion_tokens=None,
        cost_usd=None,
        cost_status=CostStatus.UNKNOWN,
        actual_model=None,
        provider=None,
        latency_ms=None,
        generation_id=None,
    )


class FakeCaller:
    """모델 ID 별로 정해 둔 동작을 실행하는 가짜 call_model."""

    def __init__(self, behaviors: Mapping[str, CallBehavior] | None = None) -> None:
        self.behaviors = dict(behaviors or {})
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> ModelCallResult:
        self.calls.append(kwargs)
        behavior = self.behaviors.get(kwargs["model"])
        if behavior is None:
            return ok()
        return await behavior(kwargs)


class FakeRecorder:
    """건호님 services/requests.py 가 해 줄 조건부 상태 변경을 메모리로 흉내 낸다."""

    def __init__(self, slots: Sequence[SlotPlan] = ()) -> None:
        self.created: list[NewRequest] = []
        self.statuses: dict[uuid.UUID, RequestStatus] = {
            s.request_id: R.PENDING for s in slots
        }
        self.records: dict[uuid.UUID, SlotRecord] = {}
        self.payloads: dict[uuid.UUID, tuple[list[dict[str, str]], str | None]] = {}
        self.fail_on_record: set[uuid.UUID] = set()

    async def create_pending(self, request: NewRequest) -> None:
        self.created.append(request)
        self.statuses[request.request_id] = R.PENDING

    async def mark_running(self, request_id: uuid.UUID, now: datetime) -> bool:
        if self.statuses[request_id] != R.PENDING:
            return False
        self.statuses[request_id] = R.RUNNING
        return True

    async def record_finished(
        self, request_id: uuid.UUID, record: SlotRecord, now: datetime
    ) -> bool:
        if request_id in self.fail_on_record:
            raise RuntimeError("DB 오류")
        if self.statuses[request_id] != R.RUNNING:
            return False
        self.statuses[request_id] = record.status
        self.records[request_id] = record
        return True

    async def save_payload(
        self,
        request_id: uuid.UUID,
        messages: list[dict[str, str]],
        response_text: str | None,
    ) -> None:
        self.payloads[request_id] = (messages, response_text)

    def cancel_if_open(self, request_id: uuid.UUID) -> bool:
        """5단계 취소가 쓸 조건부 전이. 진행 중일 때만 CANCELLED 로 바꾼다."""
        if self.statuses[request_id] in (R.PENDING, R.RUNNING):
            self.statuses[request_id] = R.CANCELLED
            return True
        return False


class FakeStore:
    """simulation_runs·simulation_results 를 메모리로 흉내 낸다."""

    def __init__(self, recorder: FakeRecorder) -> None:
        self.recorder = recorder
        self.started: list[datetime] = []
        self.heartbeats: list[datetime] = []
        self.finished: list[tuple[SimulationStatus, datetime]] = []
        self.validations: dict[uuid.UUID, SlotRecord] = {}
        self.runs: list[NewRun] = []
        self.results: list[NewResult] = []

    async def insert_run(self, run: NewRun) -> None:
        self.runs.append(run)

    async def insert_result(self, result: NewResult) -> None:
        self.results.append(result)

    async def mark_started(self, simulation_id: uuid.UUID, now: datetime) -> None:
        self.started.append(now)

    async def touch_heartbeat(self, simulation_id: uuid.UUID, now: datetime) -> None:
        self.heartbeats.append(now)

    async def save_validation(self, request_id: uuid.UUID, record: SlotRecord) -> None:
        self.validations[request_id] = record

    async def final_statuses(self, simulation_id: uuid.UUID) -> list[RequestStatus]:
        return list(self.recorder.statuses.values())

    async def mark_finished(
        self, simulation_id: uuid.UUID, status: SimulationStatus, now: datetime
    ) -> None:
        self.finished.append((status, now))


def make_slots(count: int) -> list[SlotPlan]:
    return [
        SlotPlan(
            slot_no=n,
            request_id=uuid.uuid4(),
            model_id=n,
            openrouter_model_id=f"vendor/model-{n}",
            execution_provider=f"Provider{n}",
        )
        for n in range(1, count + 1)
    ]


class Harness:
    """실행 한 번에 필요한 작업·가짜 객체 묶음."""

    def __init__(
        self,
        count: int = 3,
        behaviors: Mapping[str, CallBehavior] | None = None,
        json_schema: dict[str, Any] | None = None,
        allow_fallbacks: bool = False,
        execution_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.slots = make_slots(count)
        self.caller = FakeCaller(behaviors)
        self.recorder = FakeRecorder(self.slots)
        self.store = FakeStore(self.recorder)
        self.messages = [{"role": "user", "content": "질문"}]
        self.job = SimulationJob(
            simulation_id=uuid.uuid4(),
            slots=self.slots,
            messages=self.messages,
            json_schema=json_schema,
            execution_config=execution_config or {},
            allow_fallbacks=allow_fallbacks,
        )
        self.deps = SimulationDeps(
            caller=self.caller,
            recorder=self.recorder,
            store=self.store,
            now=lambda: NOW,
        )

    def model(self, slot_no: int) -> str:
        return self.slots[slot_no - 1].openrouter_model_id

    def request_id(self, slot_no: int) -> uuid.UUID:
        return self.slots[slot_no - 1].request_id


def never_finishes(started: asyncio.Event | None = None) -> CallBehavior:
    async def behavior(kwargs: dict[str, Any]) -> ModelCallResult:
        if started is not None:
            started.set()
        await asyncio.sleep(3600)
        return ok()

    return behavior


def until_cancelled(started: asyncio.Event | None = None) -> CallBehavior:
    """취소 신호가 켜질 때까지 기다렸다가 CANCELLED 결과를 돌려주는 가짜 call_model."""

    async def behavior(kwargs: dict[str, Any]) -> ModelCallResult:
        if started is not None:
            started.set()
        await kwargs["cancel"].wait()
        return failed(R.CANCELLED)

    return behavior


class FakeLookup:
    """접수 때 읽는 DB 내용(시나리오·모델·기존 실행·시뮬레이터 식별자)을 메모리로 흉내 낸다."""

    def __init__(self) -> None:
        self.scenarios: dict[int, ScenarioInfo] = {
            7: ScenarioInfo(
                scenario_id=7,
                is_active=True,
                default_json_schema={"type": "object", "required": ["name"]},
                default_execution_config={"temperature": 0.7, "max_tokens": 1024},
            )
        }
        self.models: dict[int, ModelInfo] = {
            n: ModelInfo(
                model_id=n,
                openrouter_model_id=f"vendor/model-{n}",
                display_name=f"Model {n}",
                status=ModelStatus.ACTIVE,
            )
            for n in range(1, 5)
        }
        self.simulations: set[uuid.UUID] = set()
        self.context = SimulatorContext(project_id=3, key_id=1, service_id=4)

    async def find_scenario(self, scenario_id: int) -> ScenarioInfo | None:
        return self.scenarios.get(scenario_id)

    async def find_models(self, model_ids: Sequence[int]) -> dict[int, ModelInfo]:
        return {mid: self.models[mid] for mid in model_ids if mid in self.models}

    async def simulation_exists(self, simulation_id: uuid.UUID) -> bool:
        return simulation_id in self.simulations

    async def simulator_context(self) -> SimulatorContext:
        return self.context

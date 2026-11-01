"""비교 실행 서비스 테스트용 가짜 객체. DB 와 OpenRouter 없이 동작을 검증한다."""

import asyncio
import itertools
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models import ModelStatus, RequestStatus, SimulationStatus
from app.openrouter.result import CallResult, CallStatus, CostSource, CostStatus
from app.schemas.simulation import ReasoningEffort
from app.services.model_parameters import ParameterSupport
from app.services.simulation_input import build_messages
from app.services.simulation_ports import (
    ImageRef,
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
    SlotState,
)

NOW = datetime(2026, 10, 29, 1, 0, tzinfo=UTC)

# 온도와 모든 추론 강도를 받는 모델. 설정 제한이 주제가 아닌 테스트의 기본값이다
FULL_PARAMETER_SUPPORT = ParameterSupport(
    temperature=True, reasoning_efforts=tuple(ReasoningEffort)
)

R = RequestStatus

CallBehavior = Callable[[dict[str, Any]], Awaitable[CallResult]]


def ok(content: str = "응답", generation_id: str = "gen") -> CallResult:
    return CallResult(
        status=CallStatus.SUCCESS,
        content=content,
        requested_model="m",
        actual_model="m",
        provider="P",
        generation_id=generation_id,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=Decimal("0.001"),
        cost_status=CostStatus.CONFIRMED,
        cost_source=CostSource.API_RESPONSE,
        started_at=NOW,
        finished_at=NOW,
        latency_ms=100,
    )


def failed(status: RequestStatus = R.FAILED) -> CallResult:
    """비용 미확인으로 끝난 호출. status 는 FAILED·TIMEOUT·CANCELLED 중 하나다."""
    return CallResult(
        status=CallStatus(status.value),
        requested_model="m",
        cost_status=CostStatus.UNKNOWN,
        started_at=NOW,
        finished_at=NOW,
        latency_ms=100,
    )


class FakeCaller:
    """모델 ID 별로 정해 둔 동작을 실행하는 가짜 call_model."""

    def __init__(self, behaviors: Mapping[str, CallBehavior] | None = None) -> None:
        self.behaviors = dict(behaviors or {})
        self.calls: list[dict[str, Any]] = []
        self._generation_ids = itertools.count(1)

    async def __call__(self, **kwargs: Any) -> CallResult:
        self.calls.append(kwargs)
        behavior = self.behaviors.get(kwargs["model_id"])
        if behavior is None:
            # OpenRouter 의 생성 ID 는 호출마다 다르다. DB 도 고유값으로 강제한다
            return ok(generation_id=f"gen-{next(self._generation_ids)}")
        return await behavior(kwargs)


class FakeRecorder:
    """services/requests.py 의 조건부 상태 변경을 메모리로 흉내 낸다."""

    def __init__(self, slots: Sequence[SlotPlan] = ()) -> None:
        self.created: list[NewRequest] = []
        self.statuses: dict[uuid.UUID, RequestStatus] = {
            s.request_id: R.PENDING for s in slots
        }
        self.records: dict[uuid.UUID, SlotRecord] = {}
        self.payloads: dict[uuid.UUID, tuple[list[dict[str, Any]], str | None]] = {}
        self.fail_on_record: set[uuid.UUID] = set()
        self.late: dict[uuid.UUID, SlotRecord] = {}

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
        messages: list[dict[str, Any]],
        response_text: str | None,
    ) -> None:
        self.payloads[request_id] = (messages, response_text)

    async def keep_late_result(
        self,
        request_id: uuid.UUID,
        messages: list[dict[str, Any]],
        record: SlotRecord,
    ) -> None:
        if self.statuses[request_id] == R.CANCELLED:
            self.late[request_id] = record

    async def cancel_if_open(self, request_id: uuid.UUID, now: datetime) -> bool:
        if self.statuses[request_id] in (R.PENDING, R.RUNNING):
            self.statuses[request_id] = R.CANCELLED
            return True
        return False


class FakeImageSource:
    """저장소를 읽는 대신 asset_id 로 정해 둔 data URL 을 돌려준다. 읽은 이미지를 기록한다."""

    def __init__(self) -> None:
        self.loaded: list[uuid.UUID] = []
        self.failing: set[uuid.UUID] = set()

    async def data_url(self, image: ImageRef) -> str:
        self.loaded.append(image.asset_id)
        if image.asset_id in self.failing:
            raise OSError("저장소 오류")
        return f"data:{image.mime_type};base64,{image.asset_id.hex}"


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
        self.known_simulations: set[uuid.UUID] = set()
        self.slot_numbers: dict[uuid.UUID, int] = {}
        self.run_assets: list[tuple[uuid.UUID, list[uuid.UUID]]] = []

    async def insert_run(self, run: NewRun) -> None:
        self.runs.append(run)

    async def insert_result(self, result: NewResult) -> None:
        self.results.append(result)
        self.known_simulations.add(result.simulation_id)
        self.slot_numbers[result.request_id] = result.slot_no

    async def insert_run_assets(
        self, simulation_id: uuid.UUID, asset_ids: Sequence[uuid.UUID]
    ) -> None:
        self.run_assets.append((simulation_id, list(asset_ids)))

    async def list_slots(self, simulation_id: uuid.UUID) -> list[SlotState] | None:
        if simulation_id not in self.known_simulations:
            return None
        return [
            SlotState(request_id, slot_no, self.recorder.statuses[request_id])
            for request_id, slot_no in sorted(
                self.slot_numbers.items(), key=lambda item: item[1]
            )
        ]

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


def make_slots(count: int, max_tokens: int = 4096) -> list[SlotPlan]:
    return [
        SlotPlan(
            slot_no=n,
            request_id=uuid.uuid4(),
            model_id=n,
            openrouter_model_id=f"vendor/model-{n}",
            execution_provider=f"Provider{n}",
            execution_config={"max_tokens": max_tokens},
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
        max_tokens: int = 4096,
        images: Sequence[ImageRef] = (),
    ) -> None:
        self.slots = make_slots(count, max_tokens)
        self.caller = FakeCaller(behaviors)
        self.recorder = FakeRecorder(self.slots)
        self.store = FakeStore(self.recorder)
        self.images = FakeImageSource()
        self.store.slot_numbers = {s.request_id: s.slot_no for s in self.slots}
        self.messages: list[dict[str, Any]] = build_messages("질문", images)
        self.job = SimulationJob(
            simulation_id=uuid.uuid4(),
            slots=self.slots,
            messages=self.messages,
            json_schema=json_schema,
            allow_fallbacks=allow_fallbacks,
            images=images,
        )
        self.store.known_simulations.add(self.job.simulation_id)
        self.deps = SimulationDeps(
            caller=self.caller,
            recorder=self.recorder,
            store=self.store,
            now=lambda: NOW,
            images=self.images,
        )

    def model(self, slot_no: int) -> str:
        return self.slots[slot_no - 1].openrouter_model_id

    def request_id(self, slot_no: int) -> uuid.UUID:
        return self.slots[slot_no - 1].request_id


def never_finishes(started: asyncio.Event | None = None) -> CallBehavior:
    async def behavior(kwargs: dict[str, Any]) -> CallResult:
        if started is not None:
            started.set()
        await asyncio.sleep(3600)
        return ok()

    return behavior


def until_cancelled(started: asyncio.Event | None = None) -> CallBehavior:
    """취소 신호가 켜질 때까지 기다렸다가 CANCELLED 결과를 돌려주는 가짜 call_model."""

    async def behavior(kwargs: dict[str, Any]) -> CallResult:
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
                supports_images=True,
                parameter_support=FULL_PARAMETER_SUPPORT,
            )
            for n in range(1, 5)
        }
        self.simulations: set[uuid.UUID] = set()
        self.images: dict[uuid.UUID, ImageRef] = {}
        self.context = SimulatorContext(project_id=3, key_id=1, service_id=4)

    async def find_scenario(self, scenario_id: int) -> ScenarioInfo | None:
        return self.scenarios.get(scenario_id)

    async def find_models(self, model_ids: Sequence[int]) -> dict[int, ModelInfo]:
        return {mid: self.models[mid] for mid in model_ids if mid in self.models}

    async def simulation_exists(self, simulation_id: uuid.UUID) -> bool:
        return simulation_id in self.simulations

    async def find_images(
        self, asset_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ImageRef]:
        return {aid: self.images[aid] for aid in asset_ids if aid in self.images}

    async def simulator_context(self) -> SimulatorContext:
        return self.context

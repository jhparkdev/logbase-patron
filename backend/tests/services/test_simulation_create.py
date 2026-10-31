import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.models import (
    CallPurpose,
    DataSource,
    ModelStatus,
    RequestStatus,
    UsageOrigin,
)
from app.models import TestType as RunType
from app.schemas.simulation import SimulationCreateRequest
from app.services.simulation_create import (
    ModelNotActiveError,
    ModelNotFoundError,
    RerunSourceNotFoundError,
    ScenarioNotFoundError,
    comparability_notes,
    create_simulation,
)
from app.services.simulation_input import (
    DEFAULT_MAX_TOKENS,
    InputRequiredError,
    build_messages,
    compute_input_hash,
)
from app.services.simulation_ports import IntakeDeps, ScenarioInfo
from app.services.simulation_validation import DuplicateModelSelectionError
from tests.services.simulation_fakes import FakeLookup, FakeRecorder, FakeStore

NOW = datetime(2026, 10, 29, 1, 0, tzinfo=UTC)
USER_ID = 1
SCENARIO_ID = 7
TEMPLATE = "다음 상품 정보로 작성하세요.\n{{product_info}}"
PRODUCT = "상품명: 린넨 셔츠"
OTHER_RUN = uuid.UUID(int=999)


class Intake:
    """접수 한 번에 필요한 가짜 객체 묶음. 새 ID 는 1, 2, 3 ... 순서로 나간다."""

    def __init__(self) -> None:
        self.lookup = FakeLookup()
        self.recorder = FakeRecorder()
        self.store = FakeStore(self.recorder)
        self._next = iter(range(1, 100))
        self.deps = IntakeDeps(
            lookup=self.lookup,
            recorder=self.recorder,
            store=self.store,
            now=lambda: NOW,
            new_id=lambda: uuid.UUID(int=next(self._next)),
        )

    def nothing_was_saved(self) -> bool:
        return not (self.recorder.created or self.store.runs or self.store.results)


def selection(model_id: int, provider: str = "DeepInfra") -> dict[str, object]:
    return {"model_id": model_id, "execution_provider": provider}


def scenario_request(**overrides: Any) -> SimulationCreateRequest:
    body: dict[str, Any] = {
        "test_type": "SCENARIO",
        "scenario_id": SCENARIO_ID,
        "prompt_text": TEMPLATE,
        "input_text": PRODUCT,
        "models": [selection(1), selection(2, "DekaLLM")],
    }
    body.update(overrides)
    return SimulationCreateRequest(**body)


def custom_request(**overrides: Any) -> SimulationCreateRequest:
    body: dict[str, Any] = {
        "test_type": "CUSTOM",
        "prompt_text": "강점을 3가지로 정리하세요.",
        "models": [selection(1), selection(2)],
    }
    body.update(overrides)
    return SimulationCreateRequest(**body)


async def test_scenario_run_is_saved_with_the_confirmed_inputs() -> None:
    intake = Intake()

    job = await create_simulation(
        scenario_request(), executed_by=USER_ID, deps=intake.deps
    )

    [run] = intake.store.runs
    assert run.simulation_id == job.simulation_id == uuid.UUID(int=1)
    assert run.rerun_of_simulation_id is None
    assert run.test_type == RunType.SCENARIO
    assert run.scenario_id == SCENARIO_ID
    # 사용자가 쓴 원본을 그대로 저장한다(합친 글이 아니다)
    assert (run.prompt_text, run.input_text) == (TEMPLATE, PRODUCT)
    assert run.input_hash == compute_input_hash(TEMPLATE, PRODUCT)
    assert run.model_count == 2
    # 보내지 않은 Schema·설정은 시나리오 기본값을 쓴다
    assert run.json_schema == {"type": "object", "required": ["name"]}
    assert run.execution_config == {"temperature": 0.7, "max_tokens": 1024}
    assert run.routing_policy == {"allow_fallbacks": False, "require_parameters": True}
    # 비용 귀속과 실행자는 서버가 정한다
    assert (run.project_id, run.key_id, run.executed_by) == (3, 1, USER_ID)
    assert run.requested_at == NOW
    assert run.data_source == DataSource.LIVE


async def test_request_values_win_over_the_scenario_defaults() -> None:
    intake = Intake()
    own_schema = {"type": "object", "required": ["title"]}
    request = scenario_request(
        json_schema=own_schema, execution_config={"max_tokens": 256}
    )

    await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    [run] = intake.store.runs
    assert run.json_schema == own_schema
    assert run.execution_config == {"temperature": 0.7, "max_tokens": 256}


async def test_one_pending_request_is_created_per_model_in_order() -> None:
    intake = Intake()

    await create_simulation(scenario_request(), executed_by=USER_ID, deps=intake.deps)

    first, second = intake.recorder.created
    assert (first.request_id, second.request_id) == (uuid.UUID(int=2), uuid.UUID(int=3))
    assert (first.model_id, first.requested_model, first.requested_provider) == (
        1,
        "vendor/model-1",
        "DeepInfra",
    )
    assert (second.model_id, second.requested_provider) == (2, "DekaLLM")
    for request in (first, second):
        assert request.simulation_id == uuid.UUID(int=1)
        assert request.usage_origin == UsageOrigin.SIMULATION
        assert request.call_purpose == CallPurpose.EXPERIMENT
        assert request.attempt_no == 1
        assert (request.project_id, request.key_id, request.service_id) == (3, 1, 4)
        assert request.executed_by == USER_ID
        assert request.requested_at == NOW
        assert request.input_hash == compute_input_hash(TEMPLATE, PRODUCT)
        assert request.execution_config == {"temperature": 0.7, "max_tokens": 1024}
    # 칸마다 고정한 업체가 호출별 정책의 order 에 들어간다
    assert first.routing_policy == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "order": ["DeepInfra"],
    }
    assert second.routing_policy["order"] == ["DekaLLM"]
    assert set(intake.recorder.statuses.values()) == {RequestStatus.PENDING}


async def test_one_result_row_is_saved_per_slot_with_the_model_snapshot() -> None:
    intake = Intake()
    intake.lookup.models[2] = intake.lookup.models[2].__class__(
        model_id=2,
        openrouter_model_id="vendor/model-2",
        display_name="Mistral Nemo",
        status=ModelStatus.ACTIVE,
    )

    await create_simulation(scenario_request(), executed_by=USER_ID, deps=intake.deps)

    first, second = intake.store.results
    assert (first.slot_no, first.model_id, first.execution_provider) == (
        1,
        1,
        "DeepInfra",
    )
    assert first.request_id == uuid.UUID(int=2)
    assert (second.slot_no, second.model_display_name_at_run) == (2, "Mistral Nemo")
    assert second.model_status_at_run == ModelStatus.ACTIVE
    assert second.request_id == uuid.UUID(int=3)


async def test_the_returned_job_is_ready_to_run() -> None:
    intake = Intake()
    request = scenario_request(routing_policy={"allow_fallbacks": True})

    job = await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert [
        (s.slot_no, s.openrouter_model_id, s.execution_provider) for s in job.slots
    ] == [
        (1, "vendor/model-1", "DeepInfra"),
        (2, "vendor/model-2", "DekaLLM"),
    ]
    assert job.messages == build_messages("다음 상품 정보로 작성하세요.\n" + PRODUCT)
    assert job.allow_fallbacks is True
    assert [slot.execution_config for slot in job.slots] == [
        {"temperature": 0.7, "max_tokens": 1024}
    ] * 2
    assert job.json_schema == {"type": "object", "required": ["name"]}


async def test_custom_run_has_no_scenario_and_no_defaults() -> None:
    intake = Intake()

    await create_simulation(custom_request(), executed_by=USER_ID, deps=intake.deps)

    [run] = intake.store.runs
    assert run.test_type == RunType.CUSTOM
    assert run.scenario_id is None
    assert run.json_schema is None
    assert run.execution_config == {"max_tokens": DEFAULT_MAX_TOKENS}
    # Schema 가 없으면 call_model 이 require_parameters 를 켜지 않으므로 그대로 기록한다
    assert run.routing_policy == {"allow_fallbacks": False, "require_parameters": False}


async def test_same_model_with_different_providers_gets_two_slots() -> None:
    intake = Intake()
    request = custom_request(
        models=[selection(1, "DeepInfra"), selection(1, "DekaLLM")]
    )

    job = await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert [s.execution_provider for s in job.slots] == ["DeepInfra", "DekaLLM"]
    assert {s.model_id for s in job.slots} == {1}


def test_slots_sharing_a_model_are_told_apart_by_provider() -> None:
    # 같은 모델을 Provider 만 바꿔 비교하는 칸에 그 사실을 적어, 화면이 결과 칸에 보여 준다
    notes = comparability_notes([(1, "DeepInfra"), (2, "DeepInfra"), (1, "DekaLLM")])

    assert notes == [
        "같은 모델, 실행 Provider DeepInfra",
        None,
        "같은 모델, 실행 Provider DekaLLM",
    ]


def test_slots_with_different_models_have_no_note() -> None:
    assert comparability_notes([(1, "DeepInfra"), (2, "DeepInfra")]) == [None, None]


async def test_the_note_is_saved_with_each_result_row() -> None:
    intake = Intake()
    request = custom_request(
        models=[selection(1, "DeepInfra"), selection(1, "DekaLLM")]
    )

    await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert [r.comparability_note for r in intake.store.results] == [
        "같은 모델, 실행 Provider DeepInfra",
        "같은 모델, 실행 Provider DekaLLM",
    ]


async def test_rerun_keeps_the_link_to_the_original_run() -> None:
    intake = Intake()
    intake.lookup.simulations.add(OTHER_RUN)

    await create_simulation(
        custom_request(rerun_of_simulation_id=str(OTHER_RUN)),
        executed_by=USER_ID,
        deps=intake.deps,
    )

    [run] = intake.store.runs
    assert run.rerun_of_simulation_id == OTHER_RUN
    assert run.simulation_id != OTHER_RUN  # 재실행은 새 ID 다


# --- 거절: 아무것도 저장하지 않는다 ---


async def test_template_without_input_is_rejected() -> None:
    intake = Intake()

    with pytest.raises(InputRequiredError):
        await create_simulation(
            scenario_request(input_text=None), executed_by=USER_ID, deps=intake.deps
        )

    assert intake.nothing_was_saved()


async def test_unknown_scenario_is_rejected() -> None:
    intake = Intake()

    with pytest.raises(ScenarioNotFoundError):
        await create_simulation(
            scenario_request(scenario_id=99), executed_by=USER_ID, deps=intake.deps
        )

    assert intake.nothing_was_saved()


async def test_a_new_run_cannot_pick_a_retired_scenario() -> None:
    intake = Intake()
    retire_the_scenario(intake)

    with pytest.raises(ScenarioNotFoundError):
        await create_simulation(
            scenario_request(), executed_by=USER_ID, deps=intake.deps
        )

    assert intake.nothing_was_saved()


def retire_the_scenario(intake: Intake) -> None:
    intake.lookup.scenarios[SCENARIO_ID] = ScenarioInfo(
        scenario_id=SCENARIO_ID,
        is_active=False,
        default_json_schema={"type": "object", "required": ["name"]},
        default_execution_config={"temperature": 0.7, "max_tokens": 1024},
    )


async def test_rerun_is_allowed_after_its_scenario_was_retired() -> None:
    # 재실행은 과거 입력과 설정을 복원하는 것이고(기준서 8.4), 실행 당시 값은 이미 실행에 복사되어 있다.
    # 시나리오가 나중에 비활성이 되어도 과거 실행을 다시 돌릴 수 있어야 한다
    intake = Intake()
    retire_the_scenario(intake)
    intake.lookup.simulations.add(OTHER_RUN)

    await create_simulation(
        scenario_request(rerun_of_simulation_id=str(OTHER_RUN)),
        executed_by=USER_ID,
        deps=intake.deps,
    )

    [run] = intake.store.runs
    assert (run.scenario_id, run.rerun_of_simulation_id) == (SCENARIO_ID, OTHER_RUN)


async def test_rerun_still_needs_the_scenario_row_to_exist() -> None:
    intake = Intake()
    intake.lookup.simulations.add(OTHER_RUN)

    with pytest.raises(ScenarioNotFoundError):
        await create_simulation(
            scenario_request(scenario_id=99, rerun_of_simulation_id=str(OTHER_RUN)),
            executed_by=USER_ID,
            deps=intake.deps,
        )

    assert intake.nothing_was_saved()


async def test_unknown_rerun_source_is_rejected() -> None:
    intake = Intake()

    with pytest.raises(RerunSourceNotFoundError):
        await create_simulation(
            custom_request(rerun_of_simulation_id=str(OTHER_RUN)),
            executed_by=USER_ID,
            deps=intake.deps,
        )

    assert intake.nothing_was_saved()


async def test_unknown_model_is_rejected_with_its_id() -> None:
    intake = Intake()

    with pytest.raises(ModelNotFoundError) as error:
        await create_simulation(
            custom_request(models=[selection(1), selection(42)]),
            executed_by=USER_ID,
            deps=intake.deps,
        )

    assert error.value.model_ids == [42]
    assert intake.nothing_was_saved()


@pytest.mark.parametrize("status", [ModelStatus.TESTING, ModelStatus.INACTIVE])
async def test_a_model_that_is_not_active_is_rejected(status: ModelStatus) -> None:
    # 일반 실행에서는 ACTIVE 모델만 고를 수 있다 (기준서 6.5)
    intake = Intake()
    intake.lookup.models[2] = intake.lookup.models[2].__class__(
        model_id=2,
        openrouter_model_id="vendor/model-2",
        display_name="Model 2",
        status=status,
    )

    with pytest.raises(ModelNotActiveError) as error:
        await create_simulation(custom_request(), executed_by=USER_ID, deps=intake.deps)

    assert error.value.model_ids == [2]
    assert intake.nothing_was_saved()


async def test_custom_prompt_with_a_placeholder_and_no_input_is_rejected() -> None:
    intake = Intake()

    with pytest.raises(InputRequiredError):
        await create_simulation(
            custom_request(prompt_text="{{x}} 를 요약"),
            executed_by=USER_ID,
            deps=intake.deps,
        )

    assert intake.nothing_was_saved()


# --- 모델별 실행 설정 ---
def tuned(
    model_id: int, provider: str = "DeepInfra", **config: Any
) -> dict[str, object]:
    return {**selection(model_id, provider), "execution_config": config}


async def test_each_slot_applies_its_own_settings_over_the_run_settings() -> None:
    intake = Intake()
    request = custom_request(
        execution_config={"max_tokens": 1000, "temperature": 0.5},
        models=[
            tuned(1, reasoning_effort="high", temperature=0.1),
            tuned(2, max_tokens=300),
        ],
    )

    job = await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    first, second = [slot.execution_config for slot in job.slots]
    assert first == {"max_tokens": 1000, "temperature": 0.1, "reasoning_effort": "high"}
    assert second == {"max_tokens": 300, "temperature": 0.5}
    # 호출 기록에도 칸마다 실제 적용값이 남는다. 실행 행에는 공통 설정이 남는다
    assert [r.execution_config for r in intake.recorder.created] == [first, second]
    [run] = intake.store.runs
    assert run.execution_config == {"max_tokens": 1000, "temperature": 0.5}


async def test_a_slot_without_settings_follows_the_scenario_defaults() -> None:
    intake = Intake()

    job = await create_simulation(
        scenario_request(models=[tuned(1, max_tokens=64), selection(2)]),
        executed_by=USER_ID,
        deps=intake.deps,
    )

    assert [s.execution_config for s in job.slots] == [
        {"temperature": 0.7, "max_tokens": 64},
        {"temperature": 0.7, "max_tokens": 1024},
    ]


async def test_same_model_and_provider_with_different_settings_runs_as_two_slots() -> (
    None
):
    intake = Intake()
    request = custom_request(
        models=[tuned(1, reasoning_effort="low"), tuned(1, reasoning_effort="high")]
    )

    job = await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert [(s.model_id, s.execution_provider) for s in job.slots] == [
        (1, "DeepInfra"),
        (1, "DeepInfra"),
    ]
    assert [r.slot_no for r in intake.store.results] == [1, 2]


async def test_same_model_provider_and_settings_are_rejected_before_saving() -> None:
    intake = Intake()
    request = custom_request(
        models=[tuned(1, max_tokens=300), tuned(1, max_tokens=300)]
    )

    with pytest.raises(DuplicateModelSelectionError):
        await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert intake.nothing_was_saved()


async def test_duplicates_are_judged_on_the_applied_settings_not_the_typed_ones() -> (
    None
):
    # 한 칸은 비워 두고 다른 칸은 공통값과 같은 값을 적으면 실제 적용 설정이 같다.
    # DB 제약은 적용 설정(해시)으로 막으므로 서버도 합친 값으로 판단해야 500 이 나지 않는다
    intake = Intake()
    request = custom_request(
        execution_config={"max_tokens": 300},
        models=[selection(1), tuned(1, max_tokens=300)],
    )

    with pytest.raises(DuplicateModelSelectionError):
        await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert intake.nothing_was_saved()


async def test_a_scenario_default_makes_an_empty_slot_equal_to_an_explicit_one() -> (
    None
):
    intake = Intake()
    request = scenario_request(
        models=[selection(1), tuned(1, temperature=0.7, max_tokens=1024)]
    )

    with pytest.raises(DuplicateModelSelectionError):
        await create_simulation(request, executed_by=USER_ID, deps=intake.deps)

    assert intake.nothing_was_saved()

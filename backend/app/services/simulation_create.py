from app.models import CallPurpose, DataSource, UsageOrigin
from app.models import TestType as RunType
from app.schemas.simulation import SimulationCreateRequest
from app.services.simulation_input import (
    build_messages,
    build_prompt_text,
    build_request_routing_policy,
    build_run_routing_policy,
    compute_input_hash,
    resolve_execution_config,
    resolve_json_schema,
    validate_input_present,
)
from app.services.simulation_ports import (
    IntakeDeps,
    ModelInfo,
    NewRequest,
    NewResult,
    NewRun,
    ScenarioInfo,
    SimulationJob,
    SlotPlan,
)
from app.services.simulation_validation import is_model_selectable

# 실제 OpenRouter 를 부르는 실행이다. mock seed 는 MOCK 으로 구분한다
RUN_DATA_SOURCE = DataSource.LIVE
FIRST_ATTEMPT = 1


class ScenarioNotFoundError(LookupError):
    """없는 시나리오를 골랐거나, 새 실행에서 비활성 시나리오를 골랐다."""


class RerunSourceNotFoundError(LookupError):
    """재실행할 원본 실행이 없다."""


class ModelNotFoundError(LookupError):
    """등록되지 않은 모델을 골랐다."""

    def __init__(self, model_ids: list[int]) -> None:
        super().__init__("등록되지 않은 모델이다")
        self.model_ids = model_ids


class ModelNotActiveError(ValueError):
    """ACTIVE 가 아닌 모델을 골랐다. 일반 실행에서는 ACTIVE 모델만 쓸 수 있다."""

    def __init__(self, model_ids: list[int]) -> None:
        super().__init__("사용 중이 아닌 모델이다")
        self.model_ids = model_ids


async def create_simulation(
    request: SimulationCreateRequest, *, executed_by: int, deps: IntakeDeps
) -> SimulationJob:
    """비교 실행 요청을 검증하고, 실행·호출 이력·칸 결과를 PENDING 으로 저장한다.

    검증이 모두 끝난 뒤에만 저장하므로 거절되면 아무것도 남지 않는다. 저장은 한 트랜잭션으로
    호출하는 쪽이 묶는다. 돌려주는 작업을 run_simulation 에 넘기면 모델 호출이 시작된다.
    """
    validate_input_present(request.prompt_text, request.input_text)
    scenario = await _find_scenario(request, deps)
    await _check_rerun_source(request, deps)
    models = await _find_selectable_models(request, deps)
    context = await deps.lookup.simulator_context()

    execution_config = resolve_execution_config(
        request.execution_config.model_dump(exclude_none=True),
        scenario.default_execution_config if scenario else None,
    )
    json_schema = resolve_json_schema(
        request.json_schema, scenario.default_json_schema if scenario else None
    )
    run_policy = build_run_routing_policy(
        allow_fallbacks=request.routing_policy.allow_fallbacks
    )
    input_hash = compute_input_hash(request.prompt_text, request.input_text)
    now = deps.now()

    simulation_id = deps.new_id()
    await deps.store.insert_run(
        NewRun(
            simulation_id=simulation_id,
            rerun_of_simulation_id=request.rerun_of_simulation_id,
            test_type=request.test_type,
            scenario_id=request.scenario_id,
            prompt_text=request.prompt_text,
            input_text=request.input_text,
            json_schema=json_schema,
            execution_config=execution_config,
            routing_policy=run_policy,
            input_hash=input_hash,
            model_count=len(request.models),
            project_id=context.project_id,
            key_id=context.key_id,
            executed_by=executed_by,
            requested_at=now,
            data_source=RUN_DATA_SOURCE,
        )
    )

    slots: list[SlotPlan] = []
    for slot_no, chosen in enumerate(request.models, start=1):
        model = models[chosen.model_id]
        request_id = deps.new_id()
        # 순서: 실행 → 호출 이력 → 칸 결과. 뒤의 것이 앞의 것을 외래키로 가리킨다
        await deps.recorder.create_pending(
            NewRequest(
                request_id=request_id,
                simulation_id=simulation_id,
                usage_origin=UsageOrigin.SIMULATION,
                call_purpose=CallPurpose.EXPERIMENT,
                attempt_no=FIRST_ATTEMPT,
                project_id=context.project_id,
                key_id=context.key_id,
                service_id=context.service_id,
                executed_by=executed_by,
                model_id=model.model_id,
                requested_model=model.openrouter_model_id,
                requested_provider=chosen.execution_provider,
                routing_policy=build_request_routing_policy(
                    run_policy, chosen.execution_provider
                ),
                execution_config=execution_config,
                input_hash=input_hash,
                requested_at=now,
                data_source=RUN_DATA_SOURCE,
            )
        )
        await deps.store.insert_result(
            NewResult(
                simulation_id=simulation_id,
                request_id=request_id,
                slot_no=slot_no,
                model_id=model.model_id,
                execution_provider=chosen.execution_provider,
                model_status_at_run=model.status,
                model_display_name_at_run=model.display_name,
            )
        )
        slots.append(
            SlotPlan(
                slot_no=slot_no,
                request_id=request_id,
                model_id=model.model_id,
                openrouter_model_id=model.openrouter_model_id,
                execution_provider=chosen.execution_provider,
            )
        )

    return SimulationJob(
        simulation_id=simulation_id,
        slots=slots,
        messages=build_messages(
            build_prompt_text(request.prompt_text, request.input_text)
        ),
        json_schema=json_schema,
        execution_config=execution_config,
        allow_fallbacks=request.routing_policy.allow_fallbacks,
    )


async def _find_scenario(
    request: SimulationCreateRequest, deps: IntakeDeps
) -> ScenarioInfo | None:
    if request.test_type != RunType.SCENARIO or request.scenario_id is None:
        return None
    scenario = await deps.lookup.find_scenario(request.scenario_id)
    if scenario is None:
        raise ScenarioNotFoundError
    # 비활성 시나리오는 새 실행에서만 제외한다. 재실행은 과거 입력과 설정을 복원하는 것이고
    # 그 값은 실행 당시 simulation_runs 에 복사되어 있으므로 시나리오가 나중에 비활성이 되어도 허용한다
    if not scenario.is_active and request.rerun_of_simulation_id is None:
        raise ScenarioNotFoundError
    return scenario


async def _check_rerun_source(
    request: SimulationCreateRequest, deps: IntakeDeps
) -> None:
    source = request.rerun_of_simulation_id
    if source is not None and not await deps.lookup.simulation_exists(source):
        raise RerunSourceNotFoundError


async def _find_selectable_models(
    request: SimulationCreateRequest, deps: IntakeDeps
) -> dict[int, ModelInfo]:
    # 같은 모델을 업체만 바꿔 두 번 고를 수 있으므로 중복을 없애고 순서는 유지한다
    wanted = list(dict.fromkeys(chosen.model_id for chosen in request.models))
    found = await deps.lookup.find_models(wanted)
    missing = [model_id for model_id in wanted if model_id not in found]
    if missing:
        raise ModelNotFoundError(missing)
    inactive = [m for m in wanted if not is_model_selectable(found[m].status)]
    if inactive:
        raise ModelNotActiveError(inactive)
    return found

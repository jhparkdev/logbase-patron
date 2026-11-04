import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models import CallPurpose, DataSource, InputType, UsageOrigin
from app.models import TestType as RunType
from app.schemas.simulation import ModelSelectionRequest, SimulationCreateRequest
from app.schemas.simulation_output import OutputType
from app.services.auto_provider import resolve_auto_providers
from app.services.model_parameters import (
    ParameterSupport,
    drop_unsupported,
    narrow_to_provider,
    reject_unsupported_overrides,
)
from app.services.simulation_input import (
    build_messages,
    build_prompt_text,
    build_request_routing_policy,
    build_run_routing_policy,
    compute_input_hash,
    resolve_execution_config,
    resolve_json_schema,
    resolve_slot_config,
    validate_input_present,
)
from app.services.simulation_output_config import build_image_execution_config
from app.services.simulation_ports import (
    ImageRef,
    IntakeDeps,
    ModelInfo,
    NewRequest,
    NewResult,
    NewRun,
    ScenarioInfo,
    SimulationJob,
    SimulatorContext,
    SlotPlan,
)
from app.services.simulation_validation import (
    ModelSelection,
    is_model_selectable,
    validate_model_selection,
)

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


class ImageNotFoundError(LookupError):
    """올리지 않았거나 없는 이미지(asset_id)를 골랐다."""

    def __init__(self, asset_ids: list[uuid.UUID]) -> None:
        super().__init__("올리지 않은 이미지다")
        self.asset_ids = asset_ids


class ImageRequiredError(ValueError):
    """이미지가 필요한 시나리오인데 이미지를 보내지 않았다."""

    def __init__(self) -> None:
        super().__init__("이미지가 필요한 시나리오다")


class ModelImageUnsupportedError(ValueError):
    """이미지를 보냈는데 고른 모델 중에 이미지를 받지 못하는 모델이 있다."""

    def __init__(self, model_ids: list[int]) -> None:
        super().__init__("이미지를 지원하지 않는 모델이다")
        self.model_ids = model_ids


class ModelImageOutputUnsupportedError(ValueError):
    """이미지 생성 실행인데 고른 모델 중에 이미지를 만들지 못하는 모델이 있다."""

    def __init__(self, model_ids: list[int]) -> None:
        super().__init__("이미지를 만들지 못하는 모델이다")
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
    images = await _find_images(request, deps)
    _check_image_rules(scenario, images, models)
    _check_output_rules(request.output_type, models)
    context = await deps.lookup.simulator_context()

    if request.output_type == OutputType.IMAGE:
        # 이미지 호출은 텍스트 설정과 Schema 를 보내지 않으므로 시나리오 기본값도 쓰지 않는다
        execution_config = build_image_execution_config(request.image_config)
        json_schema = None
        request = await _with_real_providers(request, models, None, deps)
        slot_configs = _image_slot_configs(request.models, execution_config)
    else:
        execution_config = resolve_execution_config(
            request.execution_config.model_dump(exclude_none=True)
            if request.execution_config is not None
            else None,
            scenario.default_execution_config if scenario else None,
        )
        json_schema = resolve_json_schema(
            request.json_schema, scenario.default_json_schema if scenario else None
        )
        request = await _with_real_providers(
            request, models, execution_config["max_tokens"], deps
        )
        slot_configs = _resolve_slot_configs(
            request.models,
            execution_config,
            await _slot_supports(request.models, models, deps),
        )
    shared = _RunValues(
        simulation_id=deps.new_id(),
        context=context,
        executed_by=executed_by,
        run_policy=build_run_routing_policy(
            allow_fallbacks=request.routing_policy.allow_fallbacks,
            has_json_schema=json_schema is not None,
        ),
        input_hash=compute_input_hash(request.prompt_text, request.input_text),
        now=deps.now(),
    )

    # 순서: 실행 → 호출 이력 → 칸 결과. 뒤의 것이 앞의 것을 외래키로 가리킨다
    await deps.store.insert_run(
        NewRun(
            simulation_id=shared.simulation_id,
            rerun_of_simulation_id=request.rerun_of_simulation_id,
            test_type=request.test_type,
            scenario_id=request.scenario_id,
            prompt_text=request.prompt_text,
            input_text=request.input_text,
            json_schema=json_schema,
            execution_config=execution_config,
            routing_policy=shared.run_policy,
            input_hash=shared.input_hash,
            model_count=len(request.models),
            project_id=context.project_id,
            key_id=context.key_id,
            executed_by=executed_by,
            requested_at=shared.now,
            data_source=RUN_DATA_SOURCE,
        )
    )
    if images:
        await deps.store.insert_run_assets(
            shared.simulation_id, [image.asset_id for image in images]
        )
    notes = comparability_notes(
        [(chosen.model_id, chosen.execution_provider) for chosen in request.models]
    )
    slots = [
        await _save_slot(
            slot_no, chosen, models[chosen.model_id], shared, deps, note, config
        )
        for slot_no, (chosen, note, config) in enumerate(
            zip(request.models, notes, slot_configs, strict=True), start=1
        )
    ]

    return SimulationJob(
        simulation_id=shared.simulation_id,
        slots=slots,
        messages=build_messages(
            build_prompt_text(request.prompt_text, request.input_text), images
        ),
        json_schema=json_schema,
        allow_fallbacks=request.routing_policy.allow_fallbacks,
        images=images,
        output_type=request.output_type,
    )


async def _with_real_providers(
    request: SimulationCreateRequest,
    models: dict[int, ModelInfo],
    run_max_tokens: int | None,
    deps: IntakeDeps,
) -> SimulationCreateRequest:
    """ "가장 싼 업체 자동" 칸을 실제 업체 이름으로 바꾼 요청. 이후 검증과 저장은 실제 이름만 본다."""
    resolved = await resolve_auto_providers(
        request.models,
        models,
        prompt_text=build_prompt_text(request.prompt_text, request.input_text),
        run_max_tokens=run_max_tokens,
        providers=deps.providers,
    )
    return request.model_copy(update={"models": resolved})


def _image_slot_configs(
    chosen_models: Sequence[ModelSelectionRequest], image_config: dict[str, Any]
) -> list[dict[str, Any]]:
    """이미지 실행은 모든 칸에 같은 옵션을 보낸다. 같은 모델·Provider 두 칸은 같은 비교 대상이라 거절한다."""
    configs = [dict(image_config) for _ in chosen_models]
    validate_model_selection(
        [
            ModelSelection(chosen.model_id, chosen.execution_provider, config)
            for chosen, config in zip(chosen_models, configs, strict=True)
        ]
    )
    return configs


async def _slot_supports(
    chosen_models: Sequence[ModelSelectionRequest],
    models: dict[int, ModelInfo],
    deps: IntakeDeps,
) -> list[ParameterSupport]:
    """칸마다 받을 수 있는 설정. 모델이 받는 설정 중 그 칸의 서버 업체도 받는 것만 남긴다.

    같은 모델을 업체만 바꿔 여러 칸에 고를 수 있으므로 업체 목록은 모델마다 한 번만 묻는다.
    """
    by_model = {
        model_id: await deps.providers.provider_parameters(
            models[model_id].openrouter_model_id
        )
        for model_id in dict.fromkeys(chosen.model_id for chosen in chosen_models)
    }
    supports: list[ParameterSupport] = []
    for chosen in chosen_models:
        providers = by_model[chosen.model_id]
        supports.append(
            narrow_to_provider(
                models[chosen.model_id].parameter_support,
                providers.get(chosen.execution_provider) if providers else None,
            )
        )
    return supports


def _resolve_slot_configs(
    chosen_models: Sequence[ModelSelectionRequest],
    run_config: dict[str, Any],
    supports: Sequence[ParameterSupport],
) -> list[dict[str, Any]]:
    """칸마다 적용할 설정을 정하고, 모델·Provider·설정이 모두 같은 칸이 있으면 거절한다.

    칸에 직접 넣은 설정을 그 칸의 모델·업체가 받지 못하면 거절하고, 실행 공통 설정(시나리오
    기본값 포함)은 받지 못하는 칸에서만 뺀다. 요청한 설정과 실제 호출이 달라지는 것을 막기 위해서다.
    중복은 이렇게 정한 적용 설정으로 판단한다(DB 제약과 같은 기준). 같은 모델·업체는 받을 수 있는
    설정도 같으므로 공통 설정을 빼는 일이 중복 여부를 바꾸지는 않는다.
    저장 전에 판단해야 거절되었을 때 아무것도 남지 않는다.
    """
    overrides = [
        chosen.execution_config.model_dump(exclude_none=True)
        for chosen in chosen_models
    ]
    reject_unsupported_overrides(
        [
            (chosen.model_id, support, override)
            for chosen, support, override in zip(
                chosen_models, supports, overrides, strict=True
            )
        ]
    )
    configs = [
        resolve_slot_config(drop_unsupported(support, run_config), override)
        for support, override in zip(supports, overrides, strict=True)
    ]
    validate_model_selection(
        [
            ModelSelection(chosen.model_id, chosen.execution_provider, config)
            for chosen, config in zip(chosen_models, configs, strict=True)
        ]
    )
    return configs


def comparability_notes(
    selections: Sequence[tuple[int, str]],
) -> list[str | None]:
    """칸마다 비교 조건 문구. 같은 모델을 두 칸 이상 넣었으면 그 칸들은 Provider 로 구분된다고 적는다.

    (모델 ID, 실행 Provider) 목록을 받아 같은 순서로 돌려준다. 다른 모델끼리의 비교는 문구가 없다.
    """
    counts = Counter(model_id for model_id, _ in selections)
    return [
        f"같은 모델, 실행 Provider {provider}" if counts[model_id] > 1 else None
        for model_id, provider in selections
    ]


@dataclass(frozen=True)
class _RunValues:
    """실행 한 건의 모든 칸이 똑같이 쓰는 값."""

    simulation_id: uuid.UUID
    context: SimulatorContext
    executed_by: int
    run_policy: dict[str, Any]
    input_hash: str
    now: datetime


async def _save_slot(
    slot_no: int,
    chosen: ModelSelectionRequest,
    model: ModelInfo,
    shared: _RunValues,
    deps: IntakeDeps,
    comparability_note: str | None,
    execution_config: dict[str, Any],
) -> SlotPlan:
    """모델 한 칸의 호출 이력(PENDING)과 칸 결과를 저장하고, 실행할 칸을 돌려준다."""
    request_id = deps.new_id()
    await deps.recorder.create_pending(
        NewRequest(
            request_id=request_id,
            simulation_id=shared.simulation_id,
            usage_origin=UsageOrigin.SIMULATION,
            call_purpose=CallPurpose.EXPERIMENT,
            attempt_no=FIRST_ATTEMPT,
            project_id=shared.context.project_id,
            key_id=shared.context.key_id,
            service_id=shared.context.service_id,
            executed_by=shared.executed_by,
            model_id=model.model_id,
            requested_model=model.openrouter_model_id,
            requested_provider=chosen.execution_provider,
            routing_policy=build_request_routing_policy(
                shared.run_policy, chosen.execution_provider
            ),
            execution_config=execution_config,
            input_hash=shared.input_hash,
            requested_at=shared.now,
            data_source=RUN_DATA_SOURCE,
        )
    )
    await deps.store.insert_result(
        NewResult(
            simulation_id=shared.simulation_id,
            request_id=request_id,
            slot_no=slot_no,
            model_id=model.model_id,
            execution_provider=chosen.execution_provider,
            model_status_at_run=model.status,
            model_display_name_at_run=model.display_name,
            comparability_note=comparability_note,
        )
    )
    return SlotPlan(
        slot_no=slot_no,
        request_id=request_id,
        model_id=model.model_id,
        openrouter_model_id=model.openrouter_model_id,
        execution_provider=chosen.execution_provider,
        execution_config=execution_config,
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


async def _find_images(
    request: SimulationCreateRequest, deps: IntakeDeps
) -> tuple[ImageRef, ...]:
    """요청한 순서대로 이미지를 돌려준다. 하나라도 올려 둔 적이 없거나 파일이 사라졌으면 거절한다.

    파일은 실행을 만들기 전에 확인한다. 만든 뒤에 못 읽으면 모든 칸이 실패로 남는데,
    실패 이력은 지울 수 없어 이력과 성공률에 계속 섞인다.
    """
    if not request.asset_ids:
        return ()
    found = await deps.lookup.find_images(request.asset_ids)
    missing = [
        asset_id
        for asset_id in request.asset_ids
        if asset_id not in found
        or not await deps.image_files.exists(found[asset_id].storage_path)
    ]
    if missing:
        raise ImageNotFoundError(missing)
    return tuple(found[asset_id] for asset_id in request.asset_ids)


def _check_image_rules(
    scenario: ScenarioInfo | None,
    images: Sequence[ImageRef],
    models: dict[int, ModelInfo],
) -> None:
    """이미지가 필요한 시나리오에는 이미지가, 이미지를 보내면 이미지를 받는 모델만 있어야 한다.

    모델 호출 비용이 나가기 전에 접수에서 막는다. 사용자는 고쳐서 다시 보낼 수 있다.
    """
    if scenario and scenario.input_type != InputType.TEXT and not images:
        raise ImageRequiredError
    if images:
        unsupported = [
            mid for mid, model in models.items() if not model.supports_images
        ]
        if unsupported:
            raise ModelImageUnsupportedError(unsupported)


def _check_output_rules(output_type: OutputType, models: dict[int, ModelInfo]) -> None:
    """이미지 생성 실행에는 이미지를 만드는 모델만 고를 수 있다. 비용이 나가기 전에 접수에서 막는다."""
    if output_type != OutputType.IMAGE:
        return
    unsupported = [mid for mid, model in models.items() if not model.generates_images]
    if unsupported:
        raise ModelImageOutputUnsupportedError(unsupported)


async def _find_selectable_models(
    request: SimulationCreateRequest, deps: IntakeDeps
) -> dict[int, ModelInfo]:
    # 같은 모델을 업체만 바꿔 두 번 고를 수 있으므로 중복을 없애고 순서는 유지한다
    wanted = list(dict.fromkeys(chosen.model_id for chosen in request.models))
    found = await deps.lookup.find_models(wanted)
    missing = [model_id for model_id in wanted if model_id not in found]
    if missing:
        raise ModelNotFoundError(missing)
    inactive = [
        model_id
        for model_id in wanted
        if not is_model_selectable(found[model_id].status)
    ]
    if inactive:
        raise ModelNotActiveError(inactive)
    return found

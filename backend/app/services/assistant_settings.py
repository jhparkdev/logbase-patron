"""설정 초안 검증. 실행 생성·모델 호출·데이터 변경은 하지 않는다."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelStatus
from app.openrouter.lookup_result import EndpointInfo
from app.schemas.assistant import SimulatorPatch, SimulatorState
from app.schemas.simulation import AutoProvider
from app.services.auto_provider import cheapest_provider, estimate_input_tokens
from app.services.execution_provider_catalog import EndpointCatalog
from app.services.model_detail import get_model
from app.services.model_parameters import (
    narrow_to_provider,
    parameter_support,
    unsupported_parameters,
)
from app.services.provider_ranking import Workload
from app.services.simulation_input import build_prompt_text
from app.services.simulation_lookup import DbSimulationLookup
from app.services.simulation_validation import (
    ModelSelection,
    validate_model_selection,
)


class InvalidSettingsError(ValueError):
    pass


def merge_settings(current: SimulatorState, patch: SimulatorPatch) -> SimulatorState:
    changes = patch.model_dump(exclude_unset=True)
    if "execution_config" in changes:
        changes["execution_config"] = (
            {**current.execution_config.model_dump(), **changes["execution_config"]}
            if changes["execution_config"] is not None
            else {}
        )
    # 프롬프트의 명시적 null은 빈 입력으로 바꾼다. 생략한 필드는 그대로 둔다.
    if "prompt_text" in changes and changes["prompt_text"] is None:
        changes["prompt_text"] = ""
    return SimulatorState.model_validate({**current.model_dump(), **changes})


def _cheapest_name(
    endpoints: list[EndpointInfo], prompt_text: str, max_tokens: int | None
) -> str:
    """시뮬레이터 접수와 같은 기준으로 가장 싼 업체를 고른다. 화면은 실제 업체 이름만 고를 수 있다."""
    if max_tokens is None:
        raise InvalidSettingsError(
            "최대 출력 토큰을 정하면 가장 싼 서버 업체를 고를 수 있어요."
        )
    name = cheapest_provider(
        endpoints,
        Workload(
            input_tokens=estimate_input_tokens(prompt_text), output_tokens=max_tokens
        ),
    )
    if name is None:
        raise InvalidSettingsError(
            "가장 싼 서버 업체를 정할 수 없어요. 서버 업체를 직접 지정해 주세요."
        )
    return name


async def validate_patch(
    session: AsyncSession,
    catalog: EndpointCatalog,
    current: SimulatorState,
    patch: SimulatorPatch,
) -> SimulatorPatch:
    """검증한 초안을 돌려준다. 가장 싼 업체 자동 칸은 실제 업체 이름으로 바꾼다."""
    state = merge_settings(current, patch)
    prompt_text = build_prompt_text(state.prompt_text, state.input_text)
    defaults = {}
    effective_schema = state.json_schema
    if state.scenario_id:
        scenario = await DbSimulationLookup(session).find_scenario(state.scenario_id)
        if scenario is None:
            raise InvalidSettingsError("선택한 시나리오를 다시 확인해 주세요.")
        defaults = scenario.default_execution_config
        if effective_schema is None:
            effective_schema = scenario.default_json_schema
    common = {**defaults, **state.execution_config.model_dump(exclude_none=True)}
    selections = []
    resolved_models = []
    for selected in state.models:
        item = await get_model(session, selected.model_id)
        if item is None or item.model.status != ModelStatus.ACTIVE:
            raise InvalidSettingsError(
                "현재 선택할 수 없는 모델이 있어요. 모델을 다시 선택해 주세요."
            )
        model = item.model
        endpoints = await catalog.get(model.openrouter_model_id)
        effective = {
            **common,
            **selected.execution_config.model_dump(exclude_none=True),
        }
        if selected.execution_provider == AutoProvider.AUTO_CHEAPEST:
            selected = selected.model_copy(
                update={
                    "execution_provider": _cheapest_name(
                        endpoints, prompt_text, effective.get("max_tokens")
                    )
                }
            )
        endpoint = next(
            (
                entry
                for entry in endpoints
                if entry.provider_name == selected.execution_provider
            ),
            None,
        )
        if endpoint is None:
            raise InvalidSettingsError("선택한 서버 업체를 확인할 수 없어요.")
        support = narrow_to_provider(
            parameter_support(model.supported_parameters, model.openrouter_metadata),
            endpoint.supported_parameters,
        )
        if unsupported_parameters(support, effective):
            raise InvalidSettingsError(
                "선택한 모델 또는 서버 업체가 요청한 설정을 지원하지 않아요."
            )
        if state.has_images and "image" not in model.input_modalities:
            raise InvalidSettingsError("이미지 입력을 지원하지 않는 모델이 있어요.")
        if effective_schema is not None:
            required = {"response_format", "structured_outputs"}
            if not required.intersection(model.supported_parameters):
                raise InvalidSettingsError("구조화 출력을 지원하지 않는 모델이 있어요.")
            if endpoint.supported_parameters and not required.intersection(
                endpoint.supported_parameters
            ):
                raise InvalidSettingsError(
                    "선택한 서버 업체가 구조화 출력을 지원하지 않아요."
                )
        selections.append(
            ModelSelection(selected.model_id, selected.execution_provider, effective)
        )
        resolved_models.append(selected)
    # 아직 모델을 고르지 않은 입력 초안도 편집할 수 있다.
    if selections:
        try:
            validate_model_selection(selections)
        except ValueError as error:
            raise InvalidSettingsError(
                "비교 항목은 서로 다른 조건으로 2~4개 선택해 주세요."
            ) from error
    # 모델 목록을 바꾸지 않는 초안은 화면의 현재 선택을 그대로 둔다.
    if patch.models is None:
        return patch
    return patch.model_copy(update={"models": resolved_models})

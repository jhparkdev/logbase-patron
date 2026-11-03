from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.schemas.simulation import ReasoningEffort

TEMPERATURE_PARAMETER = "temperature"
REASONING_PARAMETER = "reasoning"


@dataclass(frozen=True)
class ParameterSupport:
    """모델이 받을 수 있는 실행 설정. max_tokens 는 모든 모델이 받으므로 담지 않는다."""

    temperature: bool
    # 받을 수 있는 추론 강도. 비어 있으면 추론 강도를 받지 않는다
    reasoning_efforts: tuple[ReasoningEffort, ...]


class ModelParameterUnsupportedError(ValueError):
    """칸에 직접 넣은 설정을 그 모델이 받지 못한다."""

    def __init__(self, model_ids: list[int], parameters: list[str]) -> None:
        super().__init__("모델이 지원하지 않는 설정이다")
        self.model_ids = model_ids
        self.parameters = parameters


def parameter_support(
    supported_parameters: Collection[str],
    openrouter_metadata: Mapping[str, Any] | None = None,
) -> ParameterSupport:
    """OpenRouter 가 알려 준 지원 파라미터와 모델 정보에서 받을 수 있는 설정을 판단한다.

    강도별 지원 범위는 모델 정보의 reasoning.supported_efforts 에서 읽는다.
    그 목록이 없거나 아는 값이 하나도 없으면(목록 저장 전에 등록된 모델 등) 모든 값을 받는 것으로 본다.
    """
    return ParameterSupport(
        temperature=TEMPERATURE_PARAMETER in supported_parameters,
        reasoning_efforts=(
            _listed_efforts(openrouter_metadata) or tuple(ReasoningEffort)
            if REASONING_PARAMETER in supported_parameters
            else ()
        ),
    )


def _listed_efforts(
    openrouter_metadata: Mapping[str, Any] | None,
) -> tuple[ReasoningEffort, ...]:
    # DB 의 JSONB 라 모양을 믿지 않는다. 모르는 강도 값은 보낼 수 없으므로 뺀다
    reasoning = (openrouter_metadata or {}).get(REASONING_PARAMETER)
    listed = reasoning.get("supported_efforts") if isinstance(reasoning, dict) else None
    if not isinstance(listed, list):
        return ()
    return tuple(effort for effort in ReasoningEffort if effort.value in listed)


def unsupported_parameters(
    support: ParameterSupport, config: Mapping[str, Any]
) -> list[str]:
    """설정 중 모델이 받지 못하는 항목의 이름. config 에 적힌 순서를 따른다."""
    unsupported: list[str] = []
    for name, value in config.items():
        if (
            name == "temperature"
            and not support.temperature
            or name == "reasoning_effort"
            and value not in support.reasoning_efforts
        ):
            unsupported.append(name)
    return unsupported


def drop_unsupported(
    support: ParameterSupport, config: Mapping[str, Any]
) -> dict[str, Any]:
    """모델이 받지 못하는 항목을 뺀 새 설정. 실행 공통 설정을 칸에 맞출 때 쓴다."""
    dropped = set(unsupported_parameters(support, config))
    return {name: value for name, value in config.items() if name not in dropped}


def reject_unsupported_overrides(
    supports: Sequence[tuple[int, ParameterSupport, Mapping[str, Any]]],
) -> None:
    """칸마다 직접 넣은 설정을 검사하고, 받지 못하는 칸이 하나라도 있으면 한꺼번에 알린다."""
    model_ids: list[int] = []
    parameters: list[str] = []
    for model_id, support, override in supports:
        bad = unsupported_parameters(support, override)
        if bad:
            model_ids.append(model_id)
            parameters.extend(bad)
    if model_ids:
        raise ModelParameterUnsupportedError(
            list(dict.fromkeys(model_ids)), list(dict.fromkeys(parameters))
        )

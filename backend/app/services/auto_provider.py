"""비교 실행의 "가장 싼 업체 자동" 칸을 실제 서버 업체 이름으로 바꾼다.

예상 비용은 업체를 고르는 데만 쓰고 화면에 보이거나 저장하지 않는다. 입력 토큰은 프롬프트 글자 수로
어림하고(이미지 입력은 세지 않는다), 출력 토큰은 그 칸에 적용할 max_tokens 로 가정한다.
"""

import math
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.openrouter.lookup_result import EndpointInfo
from app.schemas.provider_ranking import DEFAULT_MIN_UPTIME
from app.schemas.simulation import AutoProvider, ModelSelectionRequest
from app.services.provider_ranking import Workload, rank_providers
from app.services.simulation_ports import ModelInfo, ProviderParameterLookup

# 토큰 하나가 대략 몇 글자인지. 정확한 토크나이저 없이 업체끼리 비교하는 데는 충분한 어림값이다
CHARS_PER_TOKEN = 4


class AutoProviderUnavailableError(Exception):
    """가장 싼 업체를 정할 수 없다(단가를 읽지 못했거나, 남은 업체가 없거나, 이미지 실행이다)."""

    def __init__(self, model_ids: list[int]) -> None:
        super().__init__("가장 싼 업체를 정할 수 없다")
        self.model_ids = model_ids


def estimate_input_tokens(prompt_text: str) -> int:
    return math.ceil(len(prompt_text) / CHARS_PER_TOKEN)


def cheapest_provider(
    endpoints: Sequence[EndpointInfo],
    workload: Workload,
    *,
    min_uptime: Decimal = DEFAULT_MIN_UPTIME,
) -> str | None:
    """예상 총비용이 가장 낮은 업체 이름. 상태나 가동률이 나쁜 업체는 빼며, 남은 업체가 없으면 None."""
    ranking = rank_providers(endpoints, workload, min_uptime=min_uptime)
    return ranking.ranked[0].name if ranking.ranked else None


async def resolve_auto_providers(
    chosen_models: Sequence[ModelSelectionRequest],
    models: Mapping[int, ModelInfo],
    *,
    prompt_text: str,
    run_max_tokens: int | None,
    providers: ProviderParameterLookup,
) -> list[ModelSelectionRequest]:
    """AUTO_CHEAPEST 칸만 가장 싼 업체 이름으로 바꾼 선택 목록. 나머지 칸은 그대로다.

    run_max_tokens 는 실행 공통 max_tokens 이고, 이미지 실행처럼 글 출력이 없으면 None 이다.
    정할 수 없는 칸이 하나라도 있으면 어느 모델인지 모두 담아 거절한다. 다른 업체로 슬쩍 넘어가면
    사용자가 비교 조건을 알 수 없게 되기 때문이다.
    """
    auto_model_ids = [
        chosen.model_id
        for chosen in chosen_models
        if chosen.execution_provider == AutoProvider.AUTO_CHEAPEST
    ]
    if not auto_model_ids:
        return list(chosen_models)
    if run_max_tokens is None:
        raise AutoProviderUnavailableError(auto_model_ids)

    # 같은 모델을 여러 칸에 고를 수 있으므로 단가는 모델마다 한 번만 읽는다
    endpoints_by_model = {
        model_id: await providers.provider_endpoints(
            models[model_id].openrouter_model_id
        )
        for model_id in dict.fromkeys(auto_model_ids)
    }
    input_tokens = estimate_input_tokens(prompt_text)
    resolved: list[ModelSelectionRequest] = []
    unavailable: list[int] = []
    for chosen in chosen_models:
        if chosen.execution_provider != AutoProvider.AUTO_CHEAPEST:
            resolved.append(chosen)
            continue
        endpoints = endpoints_by_model[chosen.model_id]
        name = (
            cheapest_provider(
                endpoints,
                Workload(
                    input_tokens=input_tokens,
                    output_tokens=chosen.execution_config.max_tokens or run_max_tokens,
                ),
            )
            if endpoints is not None
            else None
        )
        if name is None:
            unavailable.append(chosen.model_id)
            continue
        resolved.append(chosen.model_copy(update={"execution_provider": name}))
    if unavailable:
        raise AutoProviderUnavailableError(unavailable)
    return resolved

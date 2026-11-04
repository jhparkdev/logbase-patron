"""services/auto_provider.py 테스트. "가장 싼 업체 자동" 칸을 실제 업체 이름으로 바꾸는 규칙을 본다."""

from decimal import Decimal

import pytest

from app.models import ModelStatus
from app.openrouter.lookup_result import EndpointInfo
from app.schemas.simulation import (
    MAX_TOKENS_LIMIT,
    AutoProvider,
    ModelSelectionRequest,
)
from app.services.auto_provider import (
    AutoProviderUnavailableError,
    cheapest_provider,
    estimate_input_tokens,
    resolve_auto_providers,
)
from app.services.provider_ranking import Workload
from app.services.simulation_ports import ModelInfo
from tests.services.simulation_fakes import (
    FULL_PARAMETER_SUPPORT,
    FakeProviderParameters,
)

AUTO = AutoProvider.AUTO_CHEAPEST
MIN_UPTIME = Decimal(90)
RUN_MAX_TOKENS = 1000


def endpoint(
    name: str, prompt: str, completion: str, *, status: int | None = 0
) -> EndpointInfo:
    return EndpointInfo(
        provider_name=name,
        status=status,
        pricing={"prompt": Decimal(prompt), "completion": Decimal(completion)},
    )


def model(model_id: int) -> ModelInfo:
    return ModelInfo(
        model_id=model_id,
        openrouter_model_id=f"vendor/model-{model_id}",
        display_name=f"모델 {model_id}",
        status=ModelStatus.ACTIVE,
        parameter_support=FULL_PARAMETER_SUPPORT,
    )


def selection(
    model_id: int, provider: str | AutoProvider, **config: int
) -> ModelSelectionRequest:
    return ModelSelectionRequest.model_validate(
        {
            "model_id": model_id,
            "execution_provider": provider,
            "execution_config": config,
        }
    )


MODELS = {1: model(1), 2: model(2)}

# 입력이 싸고 출력이 비싼 업체와 그 반대인 업체
INPUT_CHEAP = endpoint("InputCheap", "0.000001", "0.00001")
OUTPUT_CHEAP = endpoint("OutputCheap", "0.00001", "0.000001")


async def resolve(
    chosen: list[ModelSelectionRequest],
    providers: FakeProviderParameters,
    *,
    prompt_text: str = "안녕",
    run_max_tokens: int | None = RUN_MAX_TOKENS,
) -> list[ModelSelectionRequest]:
    return await resolve_auto_providers(
        chosen,
        MODELS,
        prompt_text=prompt_text,
        run_max_tokens=run_max_tokens,
        providers=providers,
    )


# 입력 토큰 추정


@pytest.mark.parametrize(
    ("text", "tokens"),
    [("", 0), ("a", 1), ("abcd", 1), ("abcde", 2), ("가" * 8, 2)],
)
def test_input_tokens_are_estimated_from_text_length(text: str, tokens: int) -> None:
    assert estimate_input_tokens(text) == tokens


# 가장 싼 업체 고르기


def test_the_provider_with_the_lowest_expected_cost_is_chosen() -> None:
    workload = Workload(input_tokens=10, output_tokens=1000)

    chosen = cheapest_provider(
        [INPUT_CHEAP, OUTPUT_CHEAP], workload, min_uptime=MIN_UPTIME
    )

    assert chosen == "OutputCheap"


def test_a_provider_with_a_bad_status_is_never_chosen() -> None:
    workload = Workload(input_tokens=10, output_tokens=10)
    down = endpoint("Down", "0.0000001", "0.0000001", status=1)

    chosen = cheapest_provider([down, INPUT_CHEAP], workload, min_uptime=MIN_UPTIME)

    assert chosen == "InputCheap"


def test_no_provider_is_chosen_when_none_is_left() -> None:
    workload = Workload(input_tokens=10, output_tokens=10)

    assert cheapest_provider([], workload, min_uptime=MIN_UPTIME) is None
    only_down = [endpoint("Down", "1", "1", status=1)]
    assert cheapest_provider(only_down, workload, min_uptime=MIN_UPTIME) is None


# 칸 바꾸기


async def test_selections_without_auto_are_returned_as_they_are() -> None:
    providers = FakeProviderParameters()
    chosen = [selection(1, "DeepInfra"), selection(2, "DekaLLM")]

    resolved = await resolve(chosen, providers)

    assert resolved == chosen
    assert providers.asked_endpoints == []


async def test_an_auto_slot_gets_the_cheapest_real_provider_name() -> None:
    providers = FakeProviderParameters()
    providers.endpoints_by_model["vendor/model-1"] = [INPUT_CHEAP, OUTPUT_CHEAP]
    chosen = [selection(1, AUTO), selection(2, "DekaLLM")]

    resolved = await resolve(chosen, providers, run_max_tokens=1000)

    assert [r.execution_provider for r in resolved] == ["OutputCheap", "DekaLLM"]
    assert resolved[0].model_id == 1


async def test_a_long_prompt_and_a_short_answer_favour_the_cheap_input_provider() -> (
    None
):
    providers = FakeProviderParameters()
    providers.endpoints_by_model["vendor/model-1"] = [OUTPUT_CHEAP, INPUT_CHEAP]

    [resolved] = await resolve(
        [selection(1, AUTO)],
        providers,
        prompt_text="가" * 40_000,
        run_max_tokens=10,
    )

    assert resolved.execution_provider == "InputCheap"


async def test_the_slot_max_tokens_wins_over_the_run_max_tokens() -> None:
    providers = FakeProviderParameters()
    providers.endpoints_by_model["vendor/model-1"] = [OUTPUT_CHEAP, INPUT_CHEAP]
    prompt = "가" * 400

    [by_run] = await resolve(
        [selection(1, AUTO)], providers, prompt_text=prompt, run_max_tokens=10
    )
    [by_slot] = await resolve(
        [selection(1, AUTO, max_tokens=MAX_TOKENS_LIMIT)],
        providers,
        prompt_text=prompt,
        run_max_tokens=10,
    )

    assert by_run.execution_provider == "InputCheap"
    assert by_slot.execution_provider == "OutputCheap"


async def test_the_same_model_is_looked_up_once() -> None:
    providers = FakeProviderParameters()
    providers.endpoints_by_model["vendor/model-1"] = [INPUT_CHEAP]

    await resolve([selection(1, AUTO), selection(1, AUTO, max_tokens=50)], providers)

    assert providers.asked_endpoints == ["vendor/model-1"]


async def test_the_run_is_rejected_when_prices_cannot_be_read() -> None:
    providers = FakeProviderParameters()
    # 정해 두지 않은 모델은 읽지 못한 것(None)으로 답한다
    chosen = [selection(1, AUTO), selection(2, "DekaLLM")]

    with pytest.raises(AutoProviderUnavailableError) as raised:
        await resolve(chosen, providers)

    assert raised.value.model_ids == [1]


async def test_the_run_is_rejected_when_no_provider_is_left() -> None:
    providers = FakeProviderParameters()
    providers.endpoints_by_model["vendor/model-1"] = [
        endpoint("Down", "0.000001", "0.000001", status=1)
    ]

    with pytest.raises(AutoProviderUnavailableError) as raised:
        await resolve([selection(1, AUTO)], providers)

    assert raised.value.model_ids == [1]


async def test_every_unresolvable_model_is_reported() -> None:
    providers = FakeProviderParameters()

    with pytest.raises(AutoProviderUnavailableError) as raised:
        await resolve([selection(1, AUTO), selection(2, AUTO)], providers)

    assert raised.value.model_ids == [1, 2]


async def test_an_image_run_does_not_accept_auto() -> None:
    providers = FakeProviderParameters()
    providers.endpoints_by_model["vendor/model-1"] = [INPUT_CHEAP]

    with pytest.raises(AutoProviderUnavailableError) as raised:
        await resolve([selection(1, AUTO)], providers, run_max_tokens=None)

    assert raised.value.model_ids == [1]
    assert providers.asked_endpoints == []

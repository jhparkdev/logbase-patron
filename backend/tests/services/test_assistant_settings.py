from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.openrouter.lookup_result import EndpointInfo
from app.schemas.assistant import SimulatorPatch, SimulatorState
from app.services.assistant_settings import (
    InvalidSettingsError,
    merge_settings,
    validate_patch,
)
from tests.api.model_helpers import FakeEndpointCatalog
from tests.db_helpers import Factory

# 이름순으로는 뒤에 오지만 예상 비용이 더 싼 업체다. 이름순으로 고르면 테스트가 실패한다.
CHEAP = EndpointInfo(
    provider_name="업체B",
    supported_parameters=["max_tokens"],
    pricing={"prompt": Decimal("0.000001"), "completion": Decimal("0.000002")},
)
COSTLY = EndpointInfo(
    provider_name="업체A",
    supported_parameters=["max_tokens"],
    pricing={"prompt": Decimal("0.000003"), "completion": Decimal("0.000004")},
)


def test_partial_settings_do_not_erase_prompt_models_or_other_parameters() -> None:
    current = SimulatorState(
        prompt_text="keep", execution_config={"temperature": 0.3, "max_tokens": 512}
    )
    merged = merge_settings(
        current, SimulatorPatch(execution_config={"max_tokens": 2048})
    )
    assert merged.prompt_text == "keep"
    assert merged.execution_config.temperature == 0.3
    assert merged.execution_config.max_tokens == 2048
    assert current.execution_config.max_tokens == 512


def test_explicit_null_clears_only_requested_parameter() -> None:
    current = SimulatorState(execution_config={"temperature": 0.3, "max_tokens": 512})
    merged = merge_settings(
        current, SimulatorPatch(execution_config={"max_tokens": None})
    )
    assert merged.execution_config.max_tokens is None
    assert merged.execution_config.temperature == 0.3


async def two_models(factory: Factory) -> list[int]:
    return [
        (await factory.model(status="ACTIVE", supported_parameters=["max_tokens"]))[
            "model_id"
        ]
        for _ in range(2)
    ]


def auto_patch(model_ids: list[int], **config: int) -> SimulatorPatch:
    return SimulatorPatch.model_validate(
        {
            "prompt_text": "소개해줘",
            "execution_config": config,
            "models": [
                {"model_id": model_id, "execution_provider": "AUTO_CHEAPEST"}
                for model_id in model_ids
            ],
        }
    )


async def test_auto_cheapest_becomes_the_cheapest_real_provider_name(
    db_session: AsyncSession, factory: Factory
) -> None:
    """화면은 실제 업체 이름만 고를 수 있으므로 자동 선택 값을 그대로 돌려주지 않는다."""
    model_ids = await two_models(factory)
    patch = auto_patch(model_ids, max_tokens=1024)

    resolved = await validate_patch(
        db_session, FakeEndpointCatalog([COSTLY, CHEAP]), SimulatorState(), patch
    )

    assert resolved.models is not None
    assert [item.execution_provider for item in resolved.models] == ["업체B", "업체B"]
    assert resolved.model_dump(exclude_unset=True)["execution_config"] == {
        "max_tokens": 1024
    }
    assert patch.models is not None
    assert patch.models[0].execution_provider == "AUTO_CHEAPEST"


async def test_slot_max_tokens_alone_is_enough_to_pick_the_cheapest_provider(
    db_session: AsyncSession, factory: Factory
) -> None:
    model_ids = await two_models(factory)
    patch = SimulatorPatch.model_validate(
        {
            "models": [
                {
                    "model_id": model_id,
                    "execution_provider": "AUTO_CHEAPEST",
                    "execution_config": {"max_tokens": 256 + index},
                }
                for index, model_id in enumerate(model_ids)
            ]
        }
    )

    resolved = await validate_patch(
        db_session, FakeEndpointCatalog([COSTLY, CHEAP]), SimulatorState(), patch
    )

    assert resolved.models is not None
    assert {item.execution_provider for item in resolved.models} == {"업체B"}


async def test_auto_cheapest_without_max_tokens_is_refused(
    db_session: AsyncSession, factory: Factory
) -> None:
    """출력 토큰을 모르면 예상 비용을 비교할 수 없다. 시뮬레이터 접수와 같은 판단이다."""
    model_ids = await two_models(factory)

    with pytest.raises(InvalidSettingsError, match="최대 출력 토큰"):
        await validate_patch(
            db_session,
            FakeEndpointCatalog([COSTLY, CHEAP]),
            SimulatorState(),
            auto_patch(model_ids),
        )


async def test_auto_cheapest_without_known_prices_is_refused(
    db_session: AsyncSession, factory: Factory
) -> None:
    model_ids = await two_models(factory)
    unpriced = EndpointInfo(provider_name="업체C", supported_parameters=["max_tokens"])

    with pytest.raises(InvalidSettingsError, match="가장 싼 서버 업체"):
        await validate_patch(
            db_session,
            FakeEndpointCatalog([unpriced]),
            SimulatorState(),
            auto_patch(model_ids, max_tokens=1024),
        )


async def test_named_provider_is_kept_as_requested(
    db_session: AsyncSession, factory: Factory
) -> None:
    model_ids = await two_models(factory)
    patch = SimulatorPatch.model_validate(
        {
            "execution_config": {"max_tokens": 1024},
            "models": [
                {"model_id": model_id, "execution_provider": "업체A"}
                for model_id in model_ids
            ],
        }
    )

    resolved = await validate_patch(
        db_session, FakeEndpointCatalog([COSTLY, CHEAP]), SimulatorState(), patch
    )

    assert resolved == patch

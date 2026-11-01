from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog, ModelPrice, ModelRegistry
from app.openrouter.lookup_result import ModelInfo
from app.services.model_register import (
    ModelAlreadyRegisteredError,
    ModelNotInOpenRouterError,
    register_model,
)
from tests.db_helpers import Factory

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def info(**fields: Any) -> ModelInfo:
    values: dict[str, Any] = {
        "model_id": "vendor/new",
        "name": "Vendor: New",
        "pricing": {
            "prompt": Decimal("0.000001"),
            "completion": Decimal("0.000002"),
            "input_cache_read": Decimal("0.0000001"),
        },
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "supported_parameters": ["tools", "response_format"],
        "context_length": 1000,
    }
    return ModelInfo(**{**values, **fields})


@pytest.fixture
async def user_id(factory: Factory) -> int:
    return (await factory.user())["user_id"]


async def register(
    session: AsyncSession,
    user_id: int,
    models: list[ModelInfo] | None = None,
    **overrides: Any,
) -> int:
    arguments: dict[str, Any] = {
        "openrouter_model_id": "vendor/new",
        "display_name": "새 모델",
        "purpose": None,
        **overrides,
    }
    return await register_model(
        session,
        [info()] if models is None else models,
        user_id=user_id,
        now=NOW,
        **arguments,
    )


async def stored_model(session: AsyncSession, model_id: int) -> ModelRegistry:
    model = await session.scalar(
        select(ModelRegistry).where(ModelRegistry.model_id == model_id)
    )
    assert model is not None
    return model


async def count(session: AsyncSession, table: Any) -> int:
    return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_TESTING_상태로_저장하고_OpenRouter의_정보를_채운다(
    db_session: AsyncSession, user_id: int
) -> None:
    model_id = await register(db_session, user_id, purpose="요약")

    model = await stored_model(db_session, model_id)
    assert model.status == "TESTING"
    assert model.openrouter_model_id == "vendor/new"
    assert model.provider == "vendor"
    assert model.display_name == "새 모델"
    assert model.purpose == "요약"
    assert model.input_modalities == ["text", "image"]
    assert model.output_modalities == ["text"]
    assert model.supported_parameters == ["tools", "response_format"]
    assert model.context_length == 1000
    assert model.created_by == user_id
    assert model.metadata_fetched_at == NOW


async def test_단가를_알면_첫_가격_이력도_함께_저장한다(
    db_session: AsyncSession, user_id: int
) -> None:
    model_id = await register(db_session, user_id)

    price = await db_session.scalar(
        select(ModelPrice).where(ModelPrice.model_id == model_id)
    )
    assert price is not None
    assert price.price_status == "KNOWN"
    assert price.input_price_per_token == Decimal("0.000001")
    assert price.output_price_per_token == Decimal("0.000002")
    assert price.cache_read_price_per_token == Decimal("0.0000001")
    assert price.cache_write_price_per_token is None
    assert price.execution_provider is None
    assert price.source == "OPENROUTER_MODELS"
    assert price.effective_from == NOW
    assert price.effective_to is None
    assert price.checked_at == NOW
    assert price.raw_pricing == {
        "prompt": "0.000001",
        "completion": "0.000002",
        "input_cache_read": "0.0000001",
    }


async def test_단가를_모르면_가격_행을_만들지_않는다(
    db_session: AsyncSession, user_id: int
) -> None:
    await register(db_session, user_id, models=[info(pricing={})])

    assert await count(db_session, ModelPrice) == 0
    assert await count(db_session, ModelRegistry) == 1


async def test_글자_수_한도가_0_이하이면_null로_저장한다(
    db_session: AsyncSession, user_id: int
) -> None:
    model_id = await register(db_session, user_id, models=[info(context_length=0)])

    model = await stored_model(db_session, model_id)
    assert model.context_length is None


async def test_등록하면_변경_이력에_CREATE를_남긴다(
    db_session: AsyncSession, user_id: int
) -> None:
    model_id = await register(db_session, user_id)

    log = await db_session.scalar(select(ChangeLog))
    assert log is not None
    assert log.entity_type == "models"
    assert log.entity_id == str(model_id)
    assert log.action == "CREATE"
    assert log.changed_by == user_id
    assert log.reason == "모델 등록"
    assert log.changes == {
        "openrouter_model_id": {"old": None, "new": "vendor/new"},
        "display_name": {"old": None, "new": "새 모델"},
        "status": {"old": None, "new": "TESTING"},
    }


async def test_OpenRouter_목록에_없으면_저장하지_않는다(
    db_session: AsyncSession, user_id: int
) -> None:
    with pytest.raises(ModelNotInOpenRouterError):
        await register(db_session, user_id, models=[info(model_id="other/model")])

    assert await count(db_session, ModelRegistry) == 0
    assert await count(db_session, ChangeLog) == 0


async def test_이미_등록된_모델이면_아무것도_더_저장하지_않는다(
    db_session: AsyncSession, user_id: int
) -> None:
    await register(db_session, user_id)

    with pytest.raises(ModelAlreadyRegisteredError):
        await register(db_session, user_id, display_name="다른 이름")

    assert await count(db_session, ModelRegistry) == 1
    assert await count(db_session, ModelPrice) == 1
    assert await count(db_session, ChangeLog) == 1

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog, ModelRegistry, ModelStatus
from app.services.model_registry import StatusChangeError
from app.services.model_update import (
    ModelNotFoundError,
    StatusChangeRefusedError,
    change_status,
    update_model,
)
from tests.db_helpers import Factory

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
RECENT = NOW - timedelta(hours=1)


@pytest.fixture
async def user_id(factory: Factory) -> int:
    return (await factory.user())["user_id"]


async def new_model(factory: Factory, **values: Any) -> int:
    return (await factory.model(**values))["model_id"]


async def stored(session: AsyncSession, model_id: int) -> ModelRegistry:
    model = await session.scalar(
        select(ModelRegistry).where(ModelRegistry.model_id == model_id)
    )
    assert model is not None
    return model


async def logs(session: AsyncSession) -> list[ChangeLog]:
    result = await session.scalars(select(ChangeLog).order_by(ChangeLog.log_id))
    return list(result)


# ---------------------------------------------------------------
# 표시 이름·용도 수정
# ---------------------------------------------------------------
async def test_표시_이름과_용도를_바꾸고_변경_이력을_남긴다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, display_name="옛 이름", purpose="옛 용도")

    await update_model(
        db_session, model_id, {"display_name": "새 이름", "purpose": "새 용도"}, user_id
    )

    model = await stored(db_session, model_id)
    assert (model.display_name, model.purpose) == ("새 이름", "새 용도")
    [log] = await logs(db_session)
    assert log.entity_type == "models"
    assert log.entity_id == str(model_id)
    assert log.action == "UPDATE"
    assert log.changed_by == user_id
    assert log.reason == "모델 정보 수정"
    assert log.changes == {
        "display_name": {"old": "옛 이름", "new": "새 이름"},
        "purpose": {"old": "옛 용도", "new": "새 용도"},
    }


async def test_보낸_항목만_바꾸고_나머지는_그대로_둔다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, display_name="옛 이름", purpose="옛 용도")

    await update_model(db_session, model_id, {"purpose": "새 용도"}, user_id)

    model = await stored(db_session, model_id)
    assert (model.display_name, model.purpose) == ("옛 이름", "새 용도")
    [log] = await logs(db_session)
    assert log.changes == {"purpose": {"old": "옛 용도", "new": "새 용도"}}


async def test_용도를_null로_비울_수_있다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, purpose="옛 용도")

    await update_model(db_session, model_id, {"purpose": None}, user_id)

    assert (await stored(db_session, model_id)).purpose is None
    [log] = await logs(db_session)
    assert log.changes == {"purpose": {"old": "옛 용도", "new": None}}


async def test_같은_값이면_변경_이력을_남기지_않는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, display_name="이름", purpose=None)

    await update_model(
        db_session, model_id, {"display_name": "이름", "purpose": None}, user_id
    )

    assert await logs(db_session) == []


async def test_없는_모델은_수정할_수_없다(
    db_session: AsyncSession, user_id: int
) -> None:
    with pytest.raises(ModelNotFoundError):
        await update_model(db_session, 999999, {"purpose": "용도"}, user_id)


# ---------------------------------------------------------------
# 상태 변경
# ---------------------------------------------------------------
async def test_최근_성공한_테스트가_있으면_사용_중으로_바꾸고_이력을_남긴다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, status="TESTING", last_success_test_at=RECENT)

    await change_status(db_session, model_id, ModelStatus.ACTIVE, user_id, NOW)

    model = await stored(db_session, model_id)
    assert model.status == "ACTIVE"
    assert model.activated_at == NOW
    assert model.deactivated_at is None
    [log] = await logs(db_session)
    assert log.entity_type == "models"
    assert log.entity_id == str(model_id)
    assert log.action == "STATUS_CHANGE"
    assert log.changed_by == user_id
    assert log.changes == {"status": {"old": "TESTING", "new": "ACTIVE"}}


async def test_사용_중에서_사용_중단으로_바꾸면_중단_시각을_남긴다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, status="ACTIVE")

    await change_status(db_session, model_id, ModelStatus.INACTIVE, user_id, NOW)

    model = await stored(db_session, model_id)
    assert model.status == "INACTIVE"
    assert model.deactivated_at == NOW
    assert model.activated_at is None


async def test_성공한_테스트가_없으면_거절하고_아무것도_바꾸지_않는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, status="TESTING")

    with pytest.raises(StatusChangeRefusedError) as refused:
        await change_status(db_session, model_id, ModelStatus.ACTIVE, user_id, NOW)

    assert refused.value.reason == StatusChangeError.TEST_NOT_PASSED
    assert (await stored(db_session, model_id)).status == "TESTING"
    assert await logs(db_session) == []


async def test_허용하지_않는_전이는_거절한다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    model_id = await new_model(factory, status="ACTIVE")

    with pytest.raises(StatusChangeRefusedError) as refused:
        await change_status(db_session, model_id, ModelStatus.TESTING, user_id, NOW)

    assert refused.value.reason == StatusChangeError.INVALID_STATUS_TRANSITION
    assert (await stored(db_session, model_id)).status == "ACTIVE"


async def test_없는_모델의_상태는_바꿀_수_없다(
    db_session: AsyncSession, user_id: int
) -> None:
    with pytest.raises(ModelNotFoundError):
        await change_status(db_session, 999999, ModelStatus.INACTIVE, user_id, NOW)

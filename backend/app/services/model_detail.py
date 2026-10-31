"""등록 모델 한 건 조회(P-03 상세)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import ModelPrice, ModelRegistry
from app.services.model_list import ModelListItem, current_price_condition


async def get_model(session: AsyncSession, model_id: int) -> ModelListItem | None:
    """모델 한 건과 현재 대표가격을 돌려준다. 없는 번호면 None이다."""
    price = aliased(ModelPrice)
    statement = (
        select(ModelRegistry, price)
        .outerjoin(price, current_price_condition(price))
        .where(ModelRegistry.model_id == model_id)
    )
    row = (await session.execute(statement)).first()
    if row is None:
        return None
    model, current = row
    return ModelListItem(model, current)

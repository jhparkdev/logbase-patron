"""등록 모델의 제공사 선택지(P-03)."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelRegistry


@dataclass(frozen=True)
class ProviderCount:
    provider: str
    model_count: int


async def list_providers(session: AsyncSession) -> list[ProviderCount]:
    """등록된 모델이 있는 제공사와 모델 개수를 이름순으로 돌려준다. 모델 상태와 상관없이 센다."""
    rows = await session.execute(
        select(ModelRegistry.provider, func.count())
        .group_by(ModelRegistry.provider)
        .order_by(ModelRegistry.provider)
    )
    return [ProviderCount(provider, count) for provider, count in rows.all()]

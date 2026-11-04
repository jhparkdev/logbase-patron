"""새 모델 비교 알림 목록(P-03). 기록된 비교 결과를 최근 발견한 순서로 읽는다."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelDiscovery, ModelRegistry


@dataclass(frozen=True)
class DiscoveryRow:
    discovery: ModelDiscovery
    base_model_name: str | None


async def list_discoveries(session: AsyncSession, *, limit: int) -> list[DiscoveryRow]:
    rows = await session.execute(
        select(ModelDiscovery, ModelRegistry.display_name)
        .outerjoin(
            ModelRegistry, ModelRegistry.model_id == ModelDiscovery.base_model_id
        )
        .order_by(
            ModelDiscovery.discovered_at.desc(), ModelDiscovery.discovery_id.desc()
        )
        .limit(limit)
    )
    return [DiscoveryRow(discovery, name) for discovery, name in rows.all()]

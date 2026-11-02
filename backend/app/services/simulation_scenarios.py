from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TestScenario


async def list_scenarios(
    session: AsyncSession, *, include_inactive: bool
) -> Sequence[TestScenario]:
    """시나리오를 ID 순으로 돌려준다. 순서를 고정해 조회할 때마다 선택지가 움직이지 않게 한다."""
    query = select(TestScenario).order_by(TestScenario.scenario_id)
    if not include_inactive:
        query = query.where(TestScenario.is_active)
    return (await session.scalars(query)).all()

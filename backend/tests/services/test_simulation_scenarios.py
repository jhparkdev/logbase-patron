from sqlalchemy.ext.asyncio import AsyncSession

from app.services.simulation_scenarios import list_scenarios
from tests.db_helpers import Factory


async def test_only_active_scenarios_are_listed_by_default(
    db_session: AsyncSession, factory: Factory
) -> None:
    active = await factory.scenario()
    await factory.scenario(is_active=False)

    rows = await list_scenarios(db_session, include_inactive=False)

    assert [row.scenario_id for row in rows] == [active["scenario_id"]]


async def test_inactive_scenarios_are_included_on_request(
    db_session: AsyncSession, factory: Factory
) -> None:
    active = await factory.scenario()
    inactive = await factory.scenario(is_active=False)

    rows = await list_scenarios(db_session, include_inactive=True)

    assert [row.scenario_id for row in rows] == [
        active["scenario_id"],
        inactive["scenario_id"],
    ]


async def test_the_order_is_fixed_by_id_whatever_the_name(
    db_session: AsyncSession, factory: Factory
) -> None:
    first = await factory.scenario(name="하")
    second = await factory.scenario(name="가")

    rows = await list_scenarios(db_session, include_inactive=False)

    assert [row.scenario_id for row in rows] == [
        first["scenario_id"],
        second["scenario_id"],
    ]

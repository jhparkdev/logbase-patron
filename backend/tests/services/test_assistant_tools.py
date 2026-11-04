from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.assistant import SimulatorState
from app.services.assistant_tools import AssistantTools
from tests.api.model_helpers import FakeEndpointCatalog
from tests.db_helpers import T0, Factory


async def test_only_explicit_tools_are_callable(db_session: AsyncSession) -> None:
    tools = AssistantTools(db_session, FakeEndpointCatalog([]), T0, None)
    result = await tools.execute("create_simulation", {"prompt": "run now"})
    assert "error" in result
    assert tools.patch is None


async def test_history_sources_identify_actual_runs_and_keep_empty_history_link(
    db_session: AsyncSession, factory: Factory
) -> None:
    tools = AssistantTools(db_session, FakeEndpointCatalog([]), T0, None)
    await tools.execute("list_simulations", {})
    assert len(tools.sources) == 1
    assert tools.sources[0].kind == "history"
    run = await factory.simulation_run(requested_at=T0)
    tools.sources.clear()
    await tools.execute("list_simulations", {})
    linked = [source for source in tools.sources if source.simulation_id]
    assert [source.simulation_id for source in linked] == [str(run["simulation_id"])]
    assert linked[0].requested_at == T0


async def test_detail_source_includes_the_verified_run_time(
    db_session: AsyncSession, factory: Factory
) -> None:
    run = await factory.simulation_run(requested_at=T0)
    tools = AssistantTools(db_session, FakeEndpointCatalog([]), T0, None)
    await tools.execute("get_simulation", {"simulation_id": str(run["simulation_id"])})
    assert tools.sources[0].simulation_id == str(run["simulation_id"])
    assert tools.sources[0].requested_at == T0


async def test_failed_second_patch_does_not_apply_a_partial_first_patch(
    db_session: AsyncSession,
) -> None:
    tools = AssistantTools(db_session, FakeEndpointCatalog([]), T0, None)
    assert (
        await tools.execute(
            "prepare_simulator_settings", {"execution_config": {"max_tokens": 512}}
        )
    )["prepared"]
    assert "error" in await tools.execute(
        "prepare_simulator_settings", {"execution_config": {"max_tokens": 999999}}
    )
    assert tools.patch is None


async def test_unknown_model_prices_stay_null(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    await factory.model_price(
        model_id=model["model_id"],
        price_status="UNKNOWN",
        input_price_per_token=None,
        output_price_per_token=None,
    )
    tools = AssistantTools(db_session, FakeEndpointCatalog([]), T0, None)
    result = await tools.execute("find_models", {})
    assert result["items"][0]["price"]["input_usd_per_token"] is None
    assert result["items"][0]["price"]["output_usd_per_token"] is None


async def test_a_corrected_setting_can_return_to_the_original_value(
    db_session: AsyncSession,
) -> None:
    tools = AssistantTools(
        db_session,
        FakeEndpointCatalog([]),
        T0,
        SimulatorState(execution_config={"max_tokens": 512}),
    )
    await tools.execute("prepare_simulator_settings", {"max_tokens": 1024})
    assert tools.patch is not None
    result = await tools.execute("prepare_simulator_settings", {"max_tokens": 512})
    assert result["unchanged"] is True
    assert tools.patch is None

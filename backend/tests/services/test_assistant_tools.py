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


async def test_count_queries_do_not_fetch_models_or_execution_providers(
    db_session: AsyncSession, factory: Factory
) -> None:
    for state in ("ACTIVE", "ACTIVE", "INACTIVE", "TESTING"):
        await factory.model(status=state)
    catalog = FakeEndpointCatalog([])
    tools = AssistantTools(
        db_session,
        catalog,
        T0,
        None,
        request_text="지금 사용 가능한 모델의 개수를 알려주세요",
    )
    result = await tools.execute("find_models", {})
    assert result["view"] == "count"
    assert result["total"] == 2
    assert result["items"] == []
    assert not catalog.asked


async def test_plain_lists_include_creators_without_endpoint_fetches(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.model(status="ACTIVE", provider="anthropic")
    catalog = FakeEndpointCatalog([])
    tools = AssistantTools(
        db_session, catalog, T0, None, request_text="등록된 모델 목록을 알려줘"
    )
    result = await tools.execute("find_models", {})
    assert result["view"] == "list"
    assert result["items"][0]["creator"] == "anthropic"
    assert not catalog.asked


async def test_count_and_list_use_the_same_literal_search_and_active_status(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.model(status="ACTIVE", display_name="모델 A%")
    await factory.model(status="ACTIVE", display_name="모델 AB")
    await factory.model(status="INACTIVE", display_name="과거 모델 A%")
    count = AssistantTools(
        db_session, FakeEndpointCatalog([]), T0, None, request_text="모델 개수"
    )
    listing = AssistantTools(
        db_session, FakeEndpointCatalog([]), T0, None, request_text="모델 목록"
    )
    first = await count.execute("find_models", {"q": "A%"})
    second = await listing.execute("find_models", {"q": "A%"})
    assert first["total"] == second["total"] == 1
    assert first["q"] == second["q"] == "A%"


async def test_explicit_provider_queries_and_model_selection_still_fetch_endpoints(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.model(status="ACTIVE")
    for question in ("모델의 실행 업체를 알려줘", "모델 두 개를 선택해줘"):
        catalog = FakeEndpointCatalog([])
        tools = AssistantTools(db_session, catalog, T0, None, request_text=question)
        result = await tools.execute("find_models", {})
        assert result["view"] == "providers"
        assert len(catalog.asked) == 1


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

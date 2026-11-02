import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InputType, ModelStatus
from app.services.simulation_lookup import (
    SIMULATOR_KEY_SECRET_REF,
    SIMULATOR_PROJECT_CODE,
    SIMULATOR_SERVICE_CODE,
    DbSimulationLookup,
    SimulatorContextMissingError,
)
from app.services.simulation_ports import ImageRef
from tests.db_helpers import Factory


@pytest.fixture
def lookup(db_session: AsyncSession) -> DbSimulationLookup:
    return DbSimulationLookup(db_session)


# --- 시나리오 ---


async def test_scenario_is_read_with_its_defaults(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    schema = {"type": "object", "required": ["title"]}
    row = await factory.scenario(
        default_json_schema=schema,
        default_execution_config={"temperature": 0.7, "max_tokens": 1024},
        is_active=False,
    )

    scenario = await lookup.find_scenario(row["scenario_id"])

    assert scenario is not None
    assert scenario.scenario_id == row["scenario_id"]
    assert scenario.is_active is False
    assert scenario.default_json_schema == schema
    assert scenario.default_execution_config == {"temperature": 0.7, "max_tokens": 1024}


async def test_unknown_scenario_is_none(lookup: DbSimulationLookup) -> None:
    assert await lookup.find_scenario(999_999) is None


# --- 모델 ---


async def test_models_are_read_by_id(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    active = await factory.model(status="ACTIVE", display_name="모델 A")
    testing = await factory.model(status="TESTING")

    found = await lookup.find_models([active["model_id"], testing["model_id"]])

    assert set(found) == {active["model_id"], testing["model_id"]}
    model = found[active["model_id"]]
    assert model.openrouter_model_id == active["openrouter_model_id"]
    assert model.display_name == "모델 A"
    assert model.status == ModelStatus.ACTIVE
    assert found[testing["model_id"]].status == ModelStatus.TESTING


async def test_unknown_models_are_left_out(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    # 빠진 모델을 골라내는 일은 접수 서비스가 한다. 여기서는 있는 것만 돌려준다
    known = await factory.model()

    found = await lookup.find_models([known["model_id"], 999_999])

    assert set(found) == {known["model_id"]}


async def test_no_model_ids_reads_nothing(lookup: DbSimulationLookup) -> None:
    assert await lookup.find_models([]) == {}


# --- 재실행 원본 ---


async def test_existing_simulation_is_found(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    run = await factory.simulation_run()

    assert await lookup.simulation_exists(run["simulation_id"])
    assert not await lookup.simulation_exists(uuid.uuid4())


# --- 비용 귀속 (PoC 프로젝트·Key·서비스) ---


async def _poc_attribution(
    factory: Factory, **key_values: object
) -> tuple[int, int, int]:
    project = await factory.project(
        project_code=SIMULATOR_PROJECT_CODE, project_type="POC"
    )
    service = await factory.service(
        service_code=SIMULATOR_SERVICE_CODE, service_type="PATRON"
    )
    key = await factory.api_key(
        project_id=project["project_id"],
        secret_ref=SIMULATOR_KEY_SECRET_REF,
        **key_values,
    )
    return project["project_id"], key["key_id"], service["service_id"]


async def test_simulator_context_is_the_poc_project_key_and_service(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    project_id, key_id, service_id = await _poc_attribution(factory)
    # 다른 프로젝트의 Key 는 고르지 않는다
    await factory.api_key(secret_ref="OTHER_KEY")

    context = await lookup.simulator_context()

    assert (context.project_id, context.key_id, context.service_id) == (
        project_id,
        key_id,
        service_id,
    )


async def test_an_inactive_poc_key_is_not_used(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    await _poc_attribution(factory, status="INACTIVE")

    with pytest.raises(SimulatorContextMissingError):
        await lookup.simulator_context()


async def test_missing_poc_setup_is_an_error_not_a_guess(
    lookup: DbSimulationLookup,
) -> None:
    # 귀속 대상을 모르면 임의로 붙이지 않는다. 실행을 받지 않는다
    with pytest.raises(SimulatorContextMissingError):
        await lookup.simulator_context()


# --- 이미지 ---


async def test_scenario_input_type_is_read(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    row = await factory.scenario(input_type="TEXT_IMAGE")

    scenario = await lookup.find_scenario(row["scenario_id"])

    assert scenario is not None
    assert scenario.input_type == InputType.TEXT_IMAGE


@pytest.mark.parametrize(
    ("modalities", "supports"),
    [(["text", "image"], True), (["text"], False), ([], False)],
)
async def test_a_model_supports_images_when_its_input_modalities_say_so(
    factory: Factory,
    lookup: DbSimulationLookup,
    modalities: list[str],
    supports: bool,
) -> None:
    row = await factory.model(status="ACTIVE", input_modalities=modalities)

    found = await lookup.find_models([row["model_id"]])

    assert found[row["model_id"]].supports_images is supports


@pytest.mark.parametrize(
    ("modalities", "generates"),
    [(["image"], True), (["text", "image"], True), (["text"], False), ([], False)],
)
async def test_a_model_makes_images_when_its_output_modalities_say_so(
    factory: Factory,
    lookup: DbSimulationLookup,
    modalities: list[str],
    generates: bool,
) -> None:
    row = await factory.model(status="ACTIVE", output_modalities=modalities)

    found = await lookup.find_models([row["model_id"]])

    assert found[row["model_id"]].generates_images is generates


@pytest.mark.parametrize(
    ("parameters", "temperature", "has_efforts"),
    [
        (["temperature", "reasoning"], True, True),
        (["temperature"], True, False),
        (["reasoning"], False, True),
        ([], False, False),
    ],
)
async def test_a_model_carries_what_settings_it_can_take(
    factory: Factory,
    lookup: DbSimulationLookup,
    parameters: list[str],
    temperature: bool,
    has_efforts: bool,
) -> None:
    row = await factory.model(status="ACTIVE", supported_parameters=parameters)

    found = await lookup.find_models([row["model_id"]])

    support = found[row["model_id"]].parameter_support
    assert support.temperature is temperature
    assert bool(support.reasoning_efforts) is has_efforts


async def test_uploaded_images_are_read_with_their_path_and_hash(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    asset = await factory.input_asset(
        storage_path="simulator/x.png", sha256="c" * 64, mime_type="image/png"
    )

    found = await lookup.find_images([asset["asset_id"]])

    assert found == {
        asset["asset_id"]: ImageRef(
            asset_id=asset["asset_id"],
            storage_path="simulator/x.png",
            mime_type="image/png",
            sha256="c" * 64,
        )
    }


async def test_images_that_were_never_uploaded_are_left_out(
    factory: Factory, lookup: DbSimulationLookup
) -> None:
    asset = await factory.input_asset()

    found = await lookup.find_images([asset["asset_id"], uuid.uuid4()])

    assert list(found) == [asset["asset_id"]]
    assert await lookup.find_images([]) == {}

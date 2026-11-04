"""migrations/ 테스트. 마이그레이션이 설계(v0.6)의 테이블·뷰를 만들고 되돌릴 수 있는지 확인한다.

patron_test에서만 실행된다(conftest의 migrated_database).
"""

from collections.abc import Callable
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from tests.db_helpers import Factory, expect_rejected

# 설계서 v0.6과 후속 즐겨찾기 테이블, 뷰 2개
DESIGN_TABLES = {
    "customers",
    "projects",
    "users",
    "services",
    "api_keys",
    "user_sessions",
    "models",
    "model_prices",
    "tasks",
    "test_scenarios",
    "simulation_runs",
    "ai_requests",
    "ai_request_payloads",
    "input_assets",
    "output_assets",
    "cost_adjustments",
    "simulation_run_assets",
    "simulation_results",
    "budgets",
    "subscription_costs",
    "key_usage_snapshots",
    "usage_reconciliations",
    "change_logs",
    "user_model_favorites",
    "command_code_keys",
    "model_discoveries",
}
DESIGN_VIEWS = {"v_request_facts", "v_simulation_summary"}
# Alembic이 "어디까지 적용했는지" 기록하는 테이블
ALEMBIC_VERSION_TABLE = "alembic_version"
NO_CHARGE_REVISION = "7b2e4f6a9c10"
SIMULATOR_SETTINGS_REVISION = "264258125f67"
API_KEY_SERVICE_REVISION = "3f1c9a7e2b64"
OUTPUT_ASSETS_REVISION = "a4d8e2c61f37"
COMMAND_CODE_KEYS_REVISION = "404e6f91129f"
ASSISTANT_ORIGIN_REVISION = "c5e1a9d3b702"
MODEL_DISCOVERIES_REVISION = "d7a3b81f4c26"


def _schema_objects(database_url: URL) -> tuple[set[str], set[str]]:
    """DB에 실제로 있는 (테이블 이름들, 뷰 이름들)을 읽는다. 구조만 보므로 동기 접속을 쓴다."""
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        return set(inspector.get_table_names()), set(inspector.get_view_names())
    finally:
        engine.dispose()


def test_upgrade_creates_design_tables_and_views(migrated_database: URL) -> None:
    """최신 마이그레이션의 테이블과 뷰가 정확히 생긴다."""
    tables, views = _schema_objects(migrated_database)

    assert tables == DESIGN_TABLES | {ALEMBIC_VERSION_TABLE}
    assert views == DESIGN_VIEWS


def test_models_match_migrated_schema(
    migrated_database: URL, alembic_config: Config
) -> None:
    """models.py와 마이그레이션으로 만든 DB 사이에 차이가 없다(alembic check).

    차이가 있으면 마이그레이션을 새로 만들어야 한다는 뜻이라 예외가 난다.
    """
    command.check(alembic_config)


def test_downgrade_to_base_then_upgrade_again(
    migrated_database: URL, alembic_config: Config
) -> None:
    """모두 되돌리면 설계 테이블·뷰가 사라지고, 다시 적용하면 원래대로 돌아온다."""
    command.downgrade(alembic_config, "base")
    tables, views = _schema_objects(migrated_database)
    assert tables & DESIGN_TABLES == set()
    assert views == set()

    # 다른 테스트가 계속 쓸 수 있도록 최신 상태로 되돌려 둔다.
    command.upgrade(alembic_config, "head")
    tables, views = _schema_objects(migrated_database)
    assert tables == DESIGN_TABLES | {ALEMBIC_VERSION_TABLE}
    assert views == DESIGN_VIEWS


def _run_no_charge_migration(
    session: Session, config: Config, *, upgrade: bool
) -> None:
    """같은 트랜잭션에서 실행해 검증용 이력과 DDL을 테스트 종료 시 함께 롤백한다."""
    revision = ScriptDirectory.from_config(config).get_revision(NO_CHARGE_REVISION)
    assert revision is not None
    migrate: Callable[[], None] = (
        revision.module.upgrade if upgrade else revision.module.downgrade
    )
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def test_no_charge_migration_preserves_history_and_restores_old_check(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """기존 행을 유지한 채 새 제약을 내렸다 올리고, 각 버전의 허용 값도 확인한다."""
    request = await factory.ai_request(
        status="SUCCESS",
        cost_status="CONFIRMED",
        cost_usd=Decimal("0.05"),
        cost_source="API_RESPONSE",
    )
    await db_session.run_sync(_run_no_charge_migration, alembic_config, upgrade=False)
    await expect_rejected(
        db_session,
        factory.ai_request(
            status="FAILED",
            error_type="PROVIDER_ERROR",
            cost_status="CONFIRMED",
            cost_usd=Decimal(0),
            cost_source="NO_CHARGE",
        ),
        constraint="ai_requests_cost_source_check",
    )

    await db_session.run_sync(_run_no_charge_migration, alembic_config, upgrade=True)
    restored = (
        (
            await db_session.execute(
                text("SELECT * FROM ai_requests WHERE request_id = :id"),
                {"id": request["request_id"]},
            )
        )
        .mappings()
        .one()
    )
    assert restored == request
    await factory.ai_request(
        status="FAILED",
        error_type="PROVIDER_ERROR",
        cost_status="CONFIRMED",
        cost_usd=Decimal(0),
        cost_source="NO_CHARGE",
    )


async def test_no_charge_history_blocks_downgrade_without_changing_data_or_schema(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """NO_CHARGE 이력이 있으면 명확한 오류로 멈추고 행·제약·리비전을 보존한다."""
    request = await factory.ai_request(
        status="FAILED",
        error_type="PROVIDER_ERROR",
        cost_status="CONFIRMED",
        cost_usd=Decimal(0),
        cost_source="NO_CHARGE",
    )
    checks_query = text(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'ai_requests'::regclass AND contype = 'c' ORDER BY conname"
    )
    checks_before = (await db_session.execute(checks_query)).all()
    version_before = await db_session.scalar(
        text("SELECT version_num FROM alembic_version")
    )

    with pytest.raises(DBAPIError, match="Cannot downgrade.*NO_CHARGE") as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_no_charge_migration, alembic_config, upgrade=False
            )

    assert caught.value.orig.sqlstate == "23514"
    assert (await db_session.execute(checks_query)).all() == checks_before
    assert (
        await db_session.scalar(text("SELECT version_num FROM alembic_version"))
        == version_before
    )
    preserved = (
        (
            await db_session.execute(
                text("SELECT * FROM ai_requests WHERE request_id = :id"),
                {"id": request["request_id"]},
            )
        )
        .mappings()
        .one()
    )
    assert preserved == request


def _run_settings_migration(session: Session, config: Config, *, upgrade: bool) -> None:
    revision = ScriptDirectory.from_config(config).get_revision(
        SIMULATOR_SETTINGS_REVISION
    )
    assert revision is not None
    migrate = revision.module.upgrade if upgrade else revision.module.downgrade
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def test_settings_upgrade_preserves_old_rows_and_backfills_hashes(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """이전 스키마에서 만든 행의 모든 기존 값을 보존하고 해시만 채운다."""
    await db_session.run_sync(_run_settings_migration, alembic_config, upgrade=False)
    run = await factory.simulation_run(execution_config={"temperature": 0.3})
    request = await factory.ai_request(
        usage_origin="SIMULATION",
        simulation_id=run["simulation_id"],
        execution_config={"temperature": 0.3, "reasoning": {"effort": "high"}},
    )
    result = await factory.simulation_result(
        simulation_id=run["simulation_id"], request_id=request["request_id"]
    )

    await db_session.run_sync(_run_settings_migration, alembic_config, upgrade=True)
    for table, key, original in (
        ("simulation_runs", "simulation_id", run),
        ("ai_requests", "request_id", request),
        ("simulation_results", "request_id", result),
    ):
        saved = (
            (
                await db_session.execute(
                    text(f"SELECT * FROM {table} WHERE {key} = :id"),
                    {"id": original[key]},
                )
            )
            .mappings()
            .one()
        )
        assert {column: saved[column] for column in original} == dict(original)
    assert (
        await db_session.scalar(
            text(
                "SELECT result.execution_config_hash = request.execution_config_hash "
                "FROM simulation_results result JOIN ai_requests request USING (request_id) "
                "WHERE result.request_id = :id"
            ),
            {"id": request["request_id"]},
        )
        is True
    )


@pytest.mark.parametrize("saved_data", ["request", "favorite"])
async def test_settings_downgrade_preserves_history_and_schema(
    factory: Factory, db_session: AsyncSession, alembic_config: Config, saved_data: str
) -> None:
    if saved_data == "request":
        original = await factory.ai_request(execution_config={"max_tokens": 512})
        query = text("SELECT * FROM ai_requests WHERE request_id = :id")
        params = {"id": original["request_id"]}
    else:
        original = await factory.insert(
            "user_model_favorites",
            {
                "user_id": (await factory.user())["user_id"],
                "model_id": (await factory.model())["model_id"],
                "execution_provider": "provider-a",
            },
        )
        query = text("SELECT * FROM user_model_favorites WHERE user_id = :id")
        params = {"id": original["user_id"]}
    version = await db_session.scalar(text("SELECT version_num FROM alembic_version"))
    with pytest.raises(
        DBAPIError, match="Cannot downgrade: simulator settings"
    ) as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_settings_migration, alembic_config, upgrade=False
            )
    assert caught.value.orig.sqlstate == "23514"
    assert (await db_session.execute(query, params)).mappings().one() == original
    assert (
        await db_session.scalar(text("SELECT version_num FROM alembic_version"))
        == version
    )
    assert (
        await db_session.scalar(
            text(
                "SELECT to_regclass('uq_sim_results_model_provider_config') IS NOT NULL"
            )
        )
        is True
    )


def _run_api_key_service_migration(
    session: Session, config: Config, *, upgrade: bool
) -> None:
    revision = ScriptDirectory.from_config(config).get_revision(
        API_KEY_SERVICE_REVISION
    )
    assert revision is not None
    migrate = revision.module.upgrade if upgrade else revision.module.downgrade
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def _api_key_row(session: AsyncSession, key_id: int) -> dict[str, object]:
    row = await session.execute(
        text("SELECT * FROM api_keys WHERE key_id = :id"), {"id": key_id}
    )
    return dict(row.mappings().one())


async def test_api_key_service_upgrade_keeps_existing_keys_as_null(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    await db_session.run_sync(
        _run_api_key_service_migration, alembic_config, upgrade=False
    )
    key = await factory.api_key()

    await db_session.run_sync(
        _run_api_key_service_migration, alembic_config, upgrade=True
    )

    saved = await _api_key_row(db_session, key["key_id"])
    assert saved.pop("service_id") is None
    assert saved == dict(key)


async def test_api_key_service_downgrade_stops_when_a_mapping_exists(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """Key와 서비스의 연결이 있으면 지우지 않고 멈춘다."""
    service = await factory.service()
    key = await factory.api_key(service_id=service["service_id"])
    version = await db_session.scalar(text("SELECT version_num FROM alembic_version"))

    with pytest.raises(DBAPIError, match="Cannot downgrade.*service") as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_api_key_service_migration, alembic_config, upgrade=False
            )

    assert caught.value.orig.sqlstate == "23514"
    assert await _api_key_row(db_session, key["key_id"]) == dict(key)
    assert (
        await db_session.scalar(text("SELECT version_num FROM alembic_version"))
        == version
    )


def _run_output_assets_migration(
    session: Session, config: Config, *, upgrade: bool
) -> None:
    revision = ScriptDirectory.from_config(config).get_revision(OUTPUT_ASSETS_REVISION)
    assert revision is not None
    migrate = revision.module.upgrade if upgrade else revision.module.downgrade
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def _table_exists(session: AsyncSession, table: str) -> bool:
    return bool(
        await session.scalar(
            text("SELECT to_regclass(:name) IS NOT NULL"), {"name": table}
        )
    )


async def test_output_assets_downgrade_drops_the_table_only_when_empty(
    db_session: AsyncSession, alembic_config: Config
) -> None:
    await db_session.run_sync(
        _run_output_assets_migration, alembic_config, upgrade=False
    )
    assert not await _table_exists(db_session, "output_assets")

    await db_session.run_sync(
        _run_output_assets_migration, alembic_config, upgrade=True
    )
    assert await _table_exists(db_session, "output_assets")


async def test_output_assets_downgrade_stops_when_an_image_is_recorded(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """결과 이미지 기록이 있으면 지우지 않고 멈춘다."""
    image = await factory.output_asset()
    version = await db_session.scalar(text("SELECT version_num FROM alembic_version"))

    with pytest.raises(DBAPIError, match="Cannot downgrade.*output images") as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_output_assets_migration, alembic_config, upgrade=False
            )

    assert caught.value.orig.sqlstate == "23514"
    saved = await db_session.execute(
        text("SELECT * FROM output_assets WHERE output_asset_id = :id"),
        {"id": image["output_asset_id"]},
    )
    assert dict(saved.mappings().one()) == dict(image)
    assert (
        await db_session.scalar(text("SELECT version_num FROM alembic_version"))
        == version
    )


def _run_command_code_keys_migration(
    session: Session, config: Config, *, upgrade: bool
) -> None:
    revision = ScriptDirectory.from_config(config).get_revision(
        COMMAND_CODE_KEYS_REVISION
    )
    assert revision is not None
    migrate = revision.module.upgrade if upgrade else revision.module.downgrade
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def test_command_code_keys_downgrade_drops_the_table_only_when_empty(
    db_session: AsyncSession, alembic_config: Config
) -> None:
    await db_session.run_sync(
        _run_command_code_keys_migration, alembic_config, upgrade=False
    )
    assert not await _table_exists(db_session, "command_code_keys")

    await db_session.run_sync(
        _run_command_code_keys_migration, alembic_config, upgrade=True
    )
    assert await _table_exists(db_session, "command_code_keys")


async def test_command_code_keys_downgrade_stops_when_a_mapping_is_registered(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """등록된 Key 매핑이 있으면 지우지 않고 멈춘다."""
    key = await factory.command_code_key()

    with pytest.raises(DBAPIError, match="Cannot downgrade.*key mappings") as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_command_code_keys_migration, alembic_config, upgrade=False
            )

    assert caught.value.orig.sqlstate == "23514"
    saved = await db_session.execute(
        text("SELECT * FROM command_code_keys WHERE command_code_key_id = :id"),
        {"id": key["command_code_key_id"]},
    )
    assert dict(saved.mappings().one()) == dict(key)


def _run_assistant_origin_migration(
    session: Session, config: Config, *, upgrade: bool
) -> None:
    """같은 트랜잭션에서 실행해 검증용 이력과 DDL을 테스트 종료 시 함께 롤백한다."""
    revision = ScriptDirectory.from_config(config).get_revision(
        ASSISTANT_ORIGIN_REVISION
    )
    assert revision is not None
    migrate: Callable[[], None] = (
        revision.module.upgrade if upgrade else revision.module.downgrade
    )
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def test_assistant_origin_migration_preserves_history_and_restores_old_check(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    """기존 이력을 유지한 채 내렸다 올리고, 각 버전에서 ASSISTANT 허용 여부를 확인한다."""
    request = await factory.ai_request(usage_origin="SIMULATION")
    await db_session.run_sync(
        _run_assistant_origin_migration, alembic_config, upgrade=False
    )
    await expect_rejected(
        db_session,
        factory.ai_request(usage_origin="ASSISTANT"),
        constraint="ai_requests_usage_origin_check",
    )
    await expect_rejected(
        db_session,
        factory.task(usage_origin="ASSISTANT"),
        constraint="tasks_usage_origin_check",
    )

    await db_session.run_sync(
        _run_assistant_origin_migration, alembic_config, upgrade=True
    )
    restored = await db_session.execute(
        text("SELECT * FROM ai_requests WHERE request_id = :id"),
        {"id": request["request_id"]},
    )
    assert restored.mappings().one() == request
    assistant = await factory.ai_request(usage_origin="ASSISTANT")
    assert assistant["owner_type"] == "POC"
    await factory.task(usage_origin="ASSISTANT")


@pytest.mark.parametrize(
    ("factory_name", "table", "key"),
    [("ai_request", "ai_requests", "request_id"), ("task", "tasks", "task_id")],
)
async def test_assistant_history_blocks_downgrade_without_changing_data_or_schema(
    factory: Factory,
    db_session: AsyncSession,
    alembic_config: Config,
    factory_name: str,
    table: str,
    key: str,
) -> None:
    """ASSISTANT 이력이 있으면 명확한 오류로 멈추고 행·제약·리비전을 보존한다."""
    row = await getattr(factory, factory_name)(usage_origin="ASSISTANT")
    checks_query = text(
        "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
        "FROM pg_constraint WHERE conrelid IN ('ai_requests'::regclass, "
        "'tasks'::regclass) AND contype = 'c' ORDER BY 1, 2"
    )
    checks_before = (await db_session.execute(checks_query)).all()
    version_before = await db_session.scalar(
        text("SELECT version_num FROM alembic_version")
    )

    with pytest.raises(DBAPIError, match="Cannot downgrade.*ASSISTANT") as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_assistant_origin_migration, alembic_config, upgrade=False
            )

    assert caught.value.orig.sqlstate == "23514"
    assert (await db_session.execute(checks_query)).all() == checks_before
    assert (
        await db_session.scalar(text("SELECT version_num FROM alembic_version"))
        == version_before
    )
    preserved = await db_session.execute(
        text(f"SELECT * FROM {table} WHERE {key} = :id"), {"id": row[key]}
    )
    assert preserved.mappings().one() == row


def _run_model_discoveries_migration(
    session: Session, config: Config, *, upgrade: bool
) -> None:
    revision = ScriptDirectory.from_config(config).get_revision(
        MODEL_DISCOVERIES_REVISION
    )
    assert revision is not None
    migrate = revision.module.upgrade if upgrade else revision.module.downgrade
    with Operations.context(MigrationContext.configure(session.connection())):
        migrate()


async def test_model_discoveries_downgrade_drops_the_table_only_when_empty(
    db_session: AsyncSession, alembic_config: Config
) -> None:
    await db_session.run_sync(
        _run_model_discoveries_migration, alembic_config, upgrade=False
    )
    assert not await _table_exists(db_session, "model_discoveries")

    await db_session.run_sync(
        _run_model_discoveries_migration, alembic_config, upgrade=True
    )
    assert await _table_exists(db_session, "model_discoveries")


async def test_model_discoveries_downgrade_stops_when_a_record_exists(
    factory: Factory, db_session: AsyncSession, alembic_config: Config
) -> None:
    await factory.model_discovery()

    with pytest.raises(DBAPIError, match="Cannot downgrade.*records") as caught:
        async with db_session.begin_nested():
            await db_session.run_sync(
                _run_model_discoveries_migration, alembic_config, upgrade=False
            )

    assert caught.value.orig.sqlstate == "23514"

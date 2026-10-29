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

# 설계서 v0.6의 테이블 22개와 뷰 2개
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
    "cost_adjustments",
    "simulation_run_assets",
    "simulation_results",
    "budgets",
    "subscription_costs",
    "key_usage_snapshots",
    "usage_reconciliations",
    "change_logs",
}
DESIGN_VIEWS = {"v_request_facts", "v_simulation_summary"}
# Alembic이 "어디까지 적용했는지" 기록하는 테이블
ALEMBIC_VERSION_TABLE = "alembic_version"
NO_CHARGE_REVISION = "7b2e4f6a9c10"


def _schema_objects(database_url: URL) -> tuple[set[str], set[str]]:
    """DB에 실제로 있는 (테이블 이름들, 뷰 이름들)을 읽는다. 구조만 보므로 동기 접속을 쓴다."""
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        return set(inspector.get_table_names()), set(inspector.get_view_names())
    finally:
        engine.dispose()


def test_upgrade_creates_design_tables_and_views(migrated_database: URL) -> None:
    """최신 마이그레이션까지 적용하면 설계의 테이블 22개, 뷰 2개가 정확히 생긴다."""
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

"""migrations/ 테스트. 마이그레이션이 설계(v0.6)의 테이블·뷰를 만들고 되돌릴 수 있는지 확인한다.

patron_test에서만 실행된다(conftest의 migrated_database).
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

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

"""app/cli.py 테스트: mock 데이터 seed 명령.

- 운영 보호: APP_ENV=production이면 --confirm-production 없이 거부한다 (DB 없이 검증).
- 적재: patron_test의 롤백되는 세션 안에서 시드를 넣고 건수를 확인한다.
- 재실행: 이미 들어가 있으면 건너뛰고 아무것도 바꾸지 않는다.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli

# 시드를 넣은 뒤 테이블별 행 수 (설계 v0.6 mock 데이터 기준)
EXPECTED_ROWS = {
    "customers": 2,
    "projects": 3,
    "users": 2,
    "services": 5,
    "api_keys": 5,
    "user_sessions": 0,
    "models": 5,
    "model_prices": 9,
    "tasks": 165,
    "test_scenarios": 5,
    "simulation_runs": 12,
    "ai_requests": 799,
    "ai_request_payloads": 33,
    "input_assets": 2,
    "cost_adjustments": 10,
    "simulation_run_assets": 2,
    "simulation_results": 33,
    "budgets": 5,
    "subscription_costs": 4,
    "key_usage_snapshots": 2,
    "usage_reconciliations": 2,
    "change_logs": 5,
}


async def _row_counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for table in EXPECTED_ROWS:
        counts[table] = await session.scalar(text(f"SELECT count(*) FROM {table}"))
    return counts


# ---------------------------------------------------------------------------
# 운영 보호 (순수 함수)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_seed_is_allowed_outside_production(app_env: str) -> None:
    cli.ensure_seed_allowed(app_env, confirm_production=False)


def test_seed_is_refused_in_production_without_confirmation() -> None:
    with pytest.raises(cli.SeedRefusedError):
        cli.ensure_seed_allowed("production", confirm_production=False)


def test_seed_is_allowed_in_production_with_confirmation() -> None:
    cli.ensure_seed_allowed("production", confirm_production=True)


# ---------------------------------------------------------------------------
# 적재와 재실행 (patron_test, 테스트가 끝나면 롤백)
# ---------------------------------------------------------------------------


async def test_seed_inserts_mock_data(db_session: AsyncSession) -> None:
    """빈 DB에 시드를 넣으면 테이블별 행 수가 mock 데이터와 같다."""
    connection = await db_session.connection()

    applied = await cli.apply_seed(connection)

    assert applied is True
    assert await _row_counts(db_session) == EXPECTED_ROWS


async def test_seed_twice_changes_nothing(db_session: AsyncSession) -> None:
    """두 번째 실행은 이미 적용된 것을 알아채고 건너뛴다(중복 키 오류 없음)."""
    connection = await db_session.connection()
    await cli.apply_seed(connection)

    applied_again = await cli.apply_seed(connection)

    assert applied_again is False
    assert await _row_counts(db_session) == EXPECTED_ROWS


async def test_ids_after_seed_do_not_collide(db_session: AsyncSession) -> None:
    """시드는 고정 ID로 넣지만 번호 생성기도 맞춰 두므로, 시드 뒤 새 행을 넣어도 ID가 겹치지 않는다."""
    connection = await db_session.connection()
    await cli.apply_seed(connection)

    new_id = await db_session.scalar(
        text(
            "INSERT INTO customers (customer_code, name) VALUES ('CUST-NEW', '새 고객') "
            "RETURNING customer_id"
        )
    )

    assert new_id == EXPECTED_ROWS["customers"] + 1


# ---------------------------------------------------------------------------
# 명령줄 (DB에 붙기 전에 막히는지)
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_runs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """실제 DB에 붙는 run_seed 대신 호출된 횟수만 기록하는 가짜를 끼운다."""
    calls: list[str] = []

    async def fake_run_seed() -> bool:
        calls.append("run")
        return True

    monkeypatch.setattr(cli, "run_seed", fake_run_seed)
    return calls


def test_cli_refuses_production_before_touching_db(
    monkeypatch: pytest.MonkeyPatch, seed_runs: list[str]
) -> None:
    """운영 환경에서 확인 옵션 없이 실행하면 DB에 붙기 전에 실패 코드로 끝난다."""
    monkeypatch.setattr(cli, "current_app_env", lambda: "production")

    exit_code = cli.main(["seed"])

    assert exit_code != 0
    assert seed_runs == []


def test_cli_runs_seed_with_confirmation_in_production(
    monkeypatch: pytest.MonkeyPatch, seed_runs: list[str]
) -> None:
    monkeypatch.setattr(cli, "current_app_env", lambda: "production")

    exit_code = cli.main(["seed", "--confirm-production"])

    assert exit_code == 0
    assert seed_runs == ["run"]


def test_cli_runs_seed_in_development(
    monkeypatch: pytest.MonkeyPatch, seed_runs: list[str]
) -> None:
    monkeypatch.setattr(cli, "current_app_env", lambda: "development")

    exit_code = cli.main(["seed"])

    assert exit_code == 0
    assert seed_runs == ["run"]

"""app/cli.py 테스트: seed와 계정·세션 관리 명령.

- 운영 보호: APP_ENV=production이면 --confirm-production 없이 거부한다 (DB 없이 검증).
- 적재: patron_test의 롤백되는 세션 안에서 시드를 넣고 건수를 확인한다.
- 재실행: 이미 들어가 있으면 건너뛰고 아무것도 바꾸지 않는다.
"""

import argparse
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from getpass import GetPassWarning

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.models import APIKey, User, UserSession
from app.services import usage_catalog
from tests.db_helpers import Factory

# 데이터 요약 시나리오에 구조화 조건을 더한 시각(KST 2026-11-02 17:00)
SCENARIO_CHANGED_AT = datetime(2026, 11, 2, 8, tzinfo=UTC)

# 시드를 넣은 뒤 테이블별 행 수 (python -m app.mock_data 가 만든 seed 기준)
EXPECTED_ROWS = {
    "customers": 6,
    "projects": 3,
    "users": 6,
    "services": 5,
    "api_keys": 17,
    "command_code_keys": 7,
    "user_sessions": 0,
    "models": 15,
    "user_model_favorites": 10,
    "model_prices": 15,
    "tasks": 2468,
    "test_scenarios": 5,
    "simulation_runs": 46,
    "ai_requests": 4753,
    "ai_request_payloads": 172,
    "input_assets": 0,
    "output_assets": 0,
    "cost_adjustments": 116,
    "simulation_run_assets": 0,
    "simulation_results": 132,
    "budgets": 9,
    "subscription_costs": 12,
    "key_usage_snapshots": 5,
    "usage_reconciliations": 4,
    "change_logs": 44,
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
    cli.ensure_command_allowed(app_env, confirm_production=False, command="seed")


def test_seed_is_refused_in_production_without_confirmation() -> None:
    with pytest.raises(cli.CommandRefusedError):
        cli.ensure_command_allowed(
            "production", confirm_production=False, command="seed"
        )


def test_seed_is_allowed_in_production_with_confirmation() -> None:
    cli.ensure_command_allowed("production", confirm_production=True, command="seed")


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


async def test_data_summary_scenario_asks_for_structured_output(
    db_session: AsyncSession,
) -> None:
    """요약 및 구조화 시나리오는 프롬프트와 Schema 둘 다 구조화를 요구한다."""
    await cli.apply_seed(await db_session.connection())

    row = (
        await db_session.execute(
            text(
                "SELECT prompt_template, default_json_schema FROM test_scenarios "
                "WHERE scenario_code = 'DATA_SUMMARY'"
            )
        )
    ).one()

    assert "JSON Schema" in row.prompt_template
    assert "{{data}}" in row.prompt_template
    assert row.default_json_schema["required"] == ["summary", "key_points"]


async def test_past_data_summary_runs_keep_the_conditions_they_ran_with(
    db_session: AsyncSession,
) -> None:
    """실행에는 당시 값을 복사해 두므로, 시나리오를 고치기 전 실행에는 Schema가 없고 뒤 실행에는 있다."""
    await cli.apply_seed(await db_session.connection())

    rows = (
        await db_session.execute(
            text(
                "SELECT run.requested_at < :changed_at AS before_change, "
                "count(*) FILTER (WHERE run.json_schema IS NOT NULL) AS with_schema, "
                "count(*) AS total "
                "FROM simulation_runs AS run JOIN test_scenarios USING (scenario_id) "
                "WHERE scenario_code = 'DATA_SUMMARY' GROUP BY 1"
            ),
            {"changed_at": SCENARIO_CHANGED_AT},
        )
    ).all()
    by_period = {row.before_change: (row.with_schema, row.total) for row in rows}

    assert by_period[True][0] == 0 and by_period[True][1] > 0
    assert by_period[False][0] == by_period[False][1] > 0


async def test_seed_refuses_a_database_with_the_previous_mock_data(
    db_session: AsyncSession,
) -> None:
    """v0.6 mock이 남은 DB에 새 seed를 겹쳐 넣지 않는다. 고정 ID가 겹치고 집계가 섞이기 때문이다."""
    await db_session.execute(
        text(
            "INSERT INTO customers (customer_code, name, is_mock) "
            "VALUES ('CUST-A', '가상고객A (패션 쇼핑몰)', true)"
        )
    )

    with pytest.raises(cli.LegacySeedError):
        await cli.apply_seed(await db_session.connection())

    assert await db_session.scalar(text("SELECT count(*) FROM ai_requests")) == 0


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


USER_CREATE_ARGS = [
    "user-create",
    "--email",
    "admin@example.test",
    "--name",
    "관리자",
    "--user-code",
    "ADMIN",
]
USER_COMMANDS = [
    USER_CREATE_ARGS,
    ["user-deactivate", "--email", "admin@example.test"],
    ["session-cleanup"],
]


def test_cli_explains_how_to_reset_when_old_mock_data_remains(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def legacy_seed() -> bool:
        raise cli.LegacySeedError

    monkeypatch.setattr(cli, "current_app_env", lambda: "development")
    monkeypatch.setattr(cli, "run_seed", legacy_seed)

    exit_code = cli.main(["seed"])

    assert exit_code == 1
    assert "초기화" in capsys.readouterr().err


@pytest.fixture
def user_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[argparse.Namespace, str | None]]:
    # 이 fixture는 명령 해석·운영 보호만 검사하도록 실제 DB 실행을 호출 기록으로 바꾼다.
    calls: list[tuple[argparse.Namespace, str | None]] = []

    async def fake_run_user_command(
        args: argparse.Namespace, password: str | None
    ) -> None:
        calls.append((args, password))

    monkeypatch.setattr(cli, "run_user_command", fake_run_user_command)
    monkeypatch.setattr(cli, "current_app_env", lambda: "development")
    return calls


@pytest.mark.parametrize("args", USER_COMMANDS)
def test_user_commands_require_production_confirmation_before_prompt_or_db(
    monkeypatch: pytest.MonkeyPatch,
    user_commands: list[tuple[argparse.Namespace, str | None]],
    args: list[str],
) -> None:
    monkeypatch.setattr(cli, "current_app_env", lambda: "production")

    def no_prompt(prompt: str) -> str:
        pytest.fail("운영 확인 전에 비밀번호를 요청하면 안 됩니다.")

    monkeypatch.setattr(cli, "getpass", no_prompt)
    assert cli.main(args) == 1
    assert user_commands == []


@pytest.mark.parametrize("args", USER_COMMANDS)
@pytest.mark.parametrize("production", [False, True])
def test_cli_dispatches_user_commands(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    user_commands: list[tuple[argparse.Namespace, str | None]],
    args: list[str],
    production: bool,
) -> None:
    password = "cli-only-secret"
    prompts: list[str] = []

    def hidden_input(prompt: str) -> str:
        prompts.append(prompt)
        return password

    monkeypatch.setattr(cli, "getpass", hidden_input)
    if production:
        monkeypatch.setattr(cli, "current_app_env", lambda: "production")
    command = [*args, "--confirm-production"] if production else args
    assert cli.main(command) == 0
    assert len(user_commands) == 1
    actual, received_password = user_commands[0]
    assert actual.command == args[0]
    assert len(prompts) == (2 if args[0] == "user-create" else 0)
    assert received_password == (password if args[0] == "user-create" else None)
    assert password not in repr(actual)
    captured = capsys.readouterr()
    assert password not in captured.out + captured.err


@pytest.mark.parametrize("password", ["", "x" * 129])
def test_cli_rejects_invalid_password_before_db(
    monkeypatch: pytest.MonkeyPatch,
    user_commands: list[tuple[argparse.Namespace, str | None]],
    password: str,
) -> None:
    monkeypatch.setattr(cli, "getpass", lambda prompt: password)
    assert cli.main(USER_CREATE_ARGS) == 1
    assert user_commands == []


def test_cli_rejects_password_confirmation_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    user_commands: list[tuple[argparse.Namespace, str | None]],
) -> None:
    passwords = iter(["first-secret", "second-secret"])
    monkeypatch.setattr(cli, "getpass", lambda prompt: next(passwords))
    assert cli.main(USER_CREATE_ARGS) == 1
    assert user_commands == []


@pytest.mark.parametrize("failure", [EOFError, KeyboardInterrupt, GetPassWarning])
def test_cli_fails_without_echoing_password_when_hidden_input_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    user_commands: list[tuple[argparse.Namespace, str | None]],
    failure: type[BaseException],
) -> None:
    def unavailable(prompt: str) -> str:
        if failure is GetPassWarning:
            warnings.warn("echo would be enabled", GetPassWarning)
            pytest.fail("숨김 입력이 불가능하면 즉시 중단해야 합니다.")
        raise failure()

    monkeypatch.setattr(cli, "getpass", unavailable)
    assert cli.main(USER_CREATE_ARGS) == 1
    assert user_commands == []


def test_cli_does_not_accept_password_as_argument(
    user_commands: list[tuple[argparse.Namespace, str | None]],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main([*USER_CREATE_ARGS, "--password", "must-not-be-accepted"])
    assert error.value.code == 2
    assert user_commands == []


def test_cli_database_errors_do_not_print_internal_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    user_commands: list[tuple[argparse.Namespace, str | None]],
) -> None:
    async def fail(args: argparse.Namespace, password: str | None) -> None:
        raise SQLAlchemyError("private-connection-info-and-password-hash")

    monkeypatch.setattr(cli, "run_user_command", fail)
    assert cli.main(["session-cleanup"]) == 1
    captured = capsys.readouterr()
    assert "DB" in captured.err
    assert "private-connection-info" not in captured.out + captured.err


async def test_user_command_runner_uses_database_and_reports_results(
    db_session: AsyncSession,
    factory: Factory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        # 명령 실행기는 그대로 사용하고 접속만 롤백되는 patron_test 세션으로 바꾼다.
        yield db_session

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: test_session)
    password = "runner-test-password"
    args = cli.make_parser().parse_args(USER_CREATE_ARGS)
    await cli.run_user_command(args, password)
    user = await db_session.scalar(select(User).where(User.user_code == "ADMIN"))
    assert user is not None
    assert "계정 생성 완료" in capsys.readouterr().out
    await factory.user_session(user_id=user.user_id)

    args = cli.make_parser().parse_args(USER_COMMANDS[1])
    await cli.run_user_command(args, None)
    await db_session.refresh(user)
    assert user.is_active is False
    assert await db_session.scalar(select(UserSession.session_id)) is None
    assert "계정 비활성화" in capsys.readouterr().out

    now = datetime.now(UTC)
    await factory.user_session(
        created_at=now - timedelta(hours=2), expires_at=now - timedelta(hours=1)
    )
    await factory.user_session(expires_at=now + timedelta(hours=1))
    args = cli.make_parser().parse_args(USER_COMMANDS[2])
    await cli.run_user_command(args, None)
    assert "만료 세션 1개 삭제 완료" in capsys.readouterr().out
    assert len((await db_session.scalars(select(UserSession.session_id))).all()) == 1


# ---------------------------------------------------------------------------
# 고객·서비스·Key 등록 명령
# ---------------------------------------------------------------------------

CUSTOMER_CREATE_ARGS = ["customer-create", "--customer-code", "C1", "--name", "고객"]
SERVICE_CREATE_ARGS = ["service-create", "--service-code", "S1", "--name", "서비스"]
KEY_REGISTER_ARGS = [
    "key-register",
    "--display-name",
    "고객 Key",
    "--secret-ref",
    "CUSTOMER_API_KEY",
    "--customer-code",
    "C1",
    "--service-code",
    "S1",
    "--environment",
    "PROD",
]
CATALOG_COMMANDS = [CUSTOMER_CREATE_ARGS, SERVICE_CREATE_ARGS, KEY_REGISTER_ARGS]


@pytest.fixture
def catalog_commands(monkeypatch: pytest.MonkeyPatch) -> list[argparse.Namespace]:
    calls: list[argparse.Namespace] = []

    async def fake_run_catalog_command(args: argparse.Namespace) -> None:
        calls.append(args)

    monkeypatch.setattr(cli, "run_catalog_command", fake_run_catalog_command)
    monkeypatch.setattr(cli, "current_app_env", lambda: "development")
    return calls


@pytest.mark.parametrize("args", CATALOG_COMMANDS)
def test_catalog_commands_require_production_confirmation_before_db(
    monkeypatch: pytest.MonkeyPatch,
    catalog_commands: list[argparse.Namespace],
    args: list[str],
) -> None:
    monkeypatch.setattr(cli, "current_app_env", lambda: "production")

    assert cli.main(args) == 1
    assert catalog_commands == []
    assert cli.main([*args, "--confirm-production"]) == 0
    assert len(catalog_commands) == 1


@pytest.mark.parametrize("args", CATALOG_COMMANDS)
def test_catalog_commands_do_not_prompt_for_a_password(
    monkeypatch: pytest.MonkeyPatch,
    catalog_commands: list[argparse.Namespace],
    args: list[str],
) -> None:
    def no_prompt(prompt: str) -> str:
        pytest.fail("등록 명령은 비밀번호를 묻지 않습니다.")

    monkeypatch.setattr(cli, "getpass", no_prompt)
    assert cli.main(args) == 0
    assert catalog_commands[0].command == args[0]


def test_service_create_defaults_to_a_customer_facing_service(
    catalog_commands: list[argparse.Namespace],
) -> None:
    assert cli.main(SERVICE_CREATE_ARGS) == 0
    assert catalog_commands[0].service_type == "CUSTOMER_FACING"


@pytest.mark.parametrize(
    "args",
    [
        [*SERVICE_CREATE_ARGS, "--service-type", "UNKNOWN"],
        [*KEY_REGISTER_ARGS[:-1], "STAGING"],
        KEY_REGISTER_ARGS[:-2],
        # Key 원문은 명령줄 인자로 받지 않는다.
        [*KEY_REGISTER_ARGS, "--secret", "must-not-be-accepted"],
    ],
)
def test_catalog_commands_reject_invalid_arguments(
    catalog_commands: list[argparse.Namespace], args: list[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    assert catalog_commands == []


def test_catalog_errors_are_reported_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    catalog_commands: list[argparse.Namespace],
) -> None:
    async def fail(args: argparse.Namespace) -> None:
        raise usage_catalog.CatalogCommandError("보여 줄 오류")

    monkeypatch.setattr(cli, "run_catalog_command", fail)
    assert cli.main(CUSTOMER_CREATE_ARGS) == 1
    assert "보여 줄 오류" in capsys.readouterr().err


async def test_catalog_command_runner_registers_rows_and_reports_ids(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: test_session)
    parser = cli.make_parser()

    await cli.run_catalog_command(parser.parse_args(CUSTOMER_CREATE_ARGS))
    assert "고객 등록 완료" in capsys.readouterr().out
    await cli.run_catalog_command(parser.parse_args(SERVICE_CREATE_ARGS))
    assert "서비스 등록 완료" in capsys.readouterr().out
    await cli.run_catalog_command(parser.parse_args(KEY_REGISTER_ARGS))
    output = capsys.readouterr().out
    assert "Key 등록 완료" in output
    assert "CUSTOMER_API_KEY" not in output

    key = await db_session.scalar(select(APIKey))
    assert key is not None
    assert key.secret_ref == "CUSTOMER_API_KEY"
    assert key.service_id is not None

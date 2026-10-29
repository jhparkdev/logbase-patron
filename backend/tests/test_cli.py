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
from app.models import User, UserSession
from tests.db_helpers import Factory

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

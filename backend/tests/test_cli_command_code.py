"""app/cli.py의 command-code-key-register 명령 테스트. 구성원과 Key 환경변수 이름을 등록한다."""

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.models import CommandCodeKey

REGISTER_ARGS = [
    "command-code-key-register",
    "--member-name",
    "홍길동",
    "--secret-ref",
    "COMMAND_CODE_KEY_HONG",
]


@pytest.fixture
def dispatched(monkeypatch: pytest.MonkeyPatch) -> list[argparse.Namespace]:
    calls: list[argparse.Namespace] = []

    async def fake_run_catalog_command(args: argparse.Namespace) -> None:
        calls.append(args)

    monkeypatch.setattr(cli, "run_catalog_command", fake_run_catalog_command)
    monkeypatch.setattr(cli, "current_app_env", lambda: "development")
    return calls


def test_등록_명령은_관리_명령으로_넘어간다(
    dispatched: list[argparse.Namespace],
) -> None:
    assert cli.main(REGISTER_ARGS) == 0

    assert dispatched[0].member_name == "홍길동"
    assert dispatched[0].secret_ref == "COMMAND_CODE_KEY_HONG"


def test_운영_환경에서는_확인_옵션_없이_거절한다(
    monkeypatch: pytest.MonkeyPatch, dispatched: list[argparse.Namespace]
) -> None:
    monkeypatch.setattr(cli, "current_app_env", lambda: "production")

    assert cli.main(REGISTER_ARGS) == 1
    assert dispatched == []
    assert cli.main([*REGISTER_ARGS, "--confirm-production"]) == 0
    assert len(dispatched) == 1


@pytest.mark.parametrize(
    "args",
    [
        REGISTER_ARGS[:-2],
        REGISTER_ARGS[:2] + REGISTER_ARGS[3:],
        # Key 원문은 명령줄 인자로 받지 않는다. 줄임말도 --secret-ref로 해석하지 않는다.
        [*REGISTER_ARGS, "--secret", "must-not-be-accepted"],
        [*REGISTER_ARGS[:-2], "--secret", "must-not-be-accepted"],
    ],
)
def test_빠진_인자와_Key_원문_인자는_거절한다(
    dispatched: list[argparse.Namespace], args: list[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(args)

    assert error.value.code == 2
    assert dispatched == []


def test_등록_오류는_스택_트레이스_없이_보여_준다(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    dispatched: list[argparse.Namespace],
) -> None:
    async def fail(args: argparse.Namespace) -> None:
        raise cli.usage_catalog.CatalogCommandError("보여 줄 오류")

    monkeypatch.setattr(cli, "run_catalog_command", fail)

    assert cli.main(REGISTER_ARGS) == 1
    assert "보여 줄 오류" in capsys.readouterr().err


async def test_실행하면_DB에_저장하고_번호만_출력한다(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    @asynccontextmanager
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(cli, "get_sessionmaker", lambda: test_session)

    await cli.run_catalog_command(cli.make_parser().parse_args(REGISTER_ARGS))

    assert "구성원 등록 완료" in capsys.readouterr().out
    key = await db_session.scalar(select(CommandCodeKey))
    assert key is not None
    assert (key.member_name, key.secret_ref) == ("홍길동", "COMMAND_CODE_KEY_HONG")

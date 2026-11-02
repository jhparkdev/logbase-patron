"""운영 명령. HTTP 경로를 늘리지 않고 명령줄로만 실행한다.

사용법 (저장소 루트에서):
    uv --directory backend run python -m app.cli seed                       # 개발 DB에 mock 데이터 넣기
    uv --directory backend run python -m app.cli seed --confirm-production  # 운영(APP_ENV=production)에서만 필요
    uv --directory backend run python -m app.cli user-create --email admin@example.test --name 관리자 --user-code ADMIN
    uv --directory backend run python -m app.cli user-deactivate --email admin@example.test
    uv --directory backend run python -m app.cli session-cleanup
    uv --directory backend run python -m app.cli customer-create --customer-code CUST-X --name 고객
    uv --directory backend run python -m app.cli service-create --service-code SVC-X --name 서비스
    uv --directory backend run python -m app.cli key-register --display-name "고객 Key" --secret-ref CUSTOMER_API_KEY --customer-code CUST-X --service-code SVC-X --environment PROD
"""

import argparse
import asyncio
import sys
import warnings
from datetime import UTC, datetime
from getpass import GetPassWarning, getpass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.models import KeyEnvironment, ServiceType
from app.schemas.auth import PASSWORD_MAX_LENGTH
from app.services import usage_catalog, users

SEED_FILE = Path(__file__).resolve().parents[1] / "seed" / "patron_mock_data_v0.6.sql"
PRODUCTION_ENV = "production"
CATALOG_COMMANDS = ("customer-create", "service-create", "key-register")
# 시드가 이미 들어갔는지 알아보는 표식: 시드가 고정 ID로 넣는 첫 mock 고객
SEED_MARKER_QUERY = text(
    "SELECT EXISTS (SELECT 1 FROM customers WHERE customer_code = 'CUST-A' AND is_mock)"
)


class CommandRefusedError(Exception):
    """운영 환경에서 확인 옵션 없이 관리 명령을 실행하려 할 때 발생한다."""


def ensure_command_allowed(
    app_env: str, confirm_production: bool, *, command: str
) -> None:
    """운영 확인은 비밀번호 입력과 DB 접속보다 먼저 한다."""
    if app_env == PRODUCTION_ENV and not confirm_production:
        raise CommandRefusedError(
            f"APP_ENV=production 에서는 --confirm-production 옵션이 있어야 {command}를 실행합니다."
        )


async def apply_seed(connection: AsyncConnection) -> bool:
    """시드를 넣고 True를 돌려준다. 이미 들어가 있으면 아무것도 하지 않고 False를 돌려준다.

    트랜잭션은 호출하는 쪽이 관리한다. 중간에 실패하면 호출한 쪽의 트랜잭션이 통째로 취소되어
    반쯤 들어간 상태가 남지 않는다.
    """
    if await connection.scalar(SEED_MARKER_QUERY):
        return False
    # 시드 SQL에는 ':', '%' 같은 문자가 들어 있다. SQLAlchemy를 거치면 파라미터 자리표시자로
    # 해석되므로, 같은 연결(같은 트랜잭션)의 psycopg 커서로 파라미터 없이 그대로 실행한다.
    raw_connection = await connection.get_raw_connection()
    async with raw_connection.driver_connection.cursor() as cursor:
        await cursor.execute(SEED_FILE.read_text(encoding="utf-8"))
    return True


async def run_seed() -> bool:
    """설정의 DATABASE_URL(개발 DB)에 시드를 한 트랜잭션으로 넣는다. 운영 확인은 호출 전에 끝낸다."""
    async with get_engine().begin() as connection:
        return await apply_seed(connection)


def current_app_env() -> str:
    return get_settings().app_env


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser(
        "seed", help="개발 DB에 mock 데이터를 넣는다 (이미 있으면 건너뜀)"
    )
    create = commands.add_parser("user-create", help="관리자 계정을 만든다")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--user-code", required=True)
    deactivate = commands.add_parser(
        "user-deactivate", help="계정을 비활성화하고 그 계정의 모든 세션을 삭제한다"
    )
    deactivate.add_argument("--email", required=True)
    cleanup = commands.add_parser(
        "session-cleanup", help="만료된 로그인 세션을 삭제한다"
    )
    customer = commands.add_parser("customer-create", help="실제 고객을 등록한다")
    customer.add_argument("--customer-code", required=True)
    customer.add_argument("--name", required=True)
    service = commands.add_parser("service-create", help="실제 서비스를 등록한다")
    service.add_argument("--service-code", required=True)
    service.add_argument("--name", required=True)
    service.add_argument(
        "--service-type",
        choices=[item.value for item in ServiceType],
        default=ServiceType.CUSTOMER_FACING.value,
    )
    # --secret 같은 줄임말이 --secret-ref로 해석되면 Key 원문을 넘기는 실수를 부추긴다.
    key = commands.add_parser(
        "key-register",
        help="고객 서비스 전용 Key를 고객·서비스에 연결한다",
        allow_abbrev=False,
    )
    key.add_argument("--display-name", required=True)
    key.add_argument(
        "--secret-ref",
        required=True,
        help="Key 원문이 든 환경변수 이름. 원문은 입력하지 않는다",
    )
    key.add_argument("--customer-code", required=True)
    key.add_argument("--service-code", required=True)
    key.add_argument(
        "--environment", choices=[item.value for item in KeyEnvironment], required=True
    )
    # 새 관리 명령도 이 목록에 넣어야 운영 확인 옵션을 함께 제공할 수 있다.
    for command in (seed, create, deactivate, cleanup, customer, service, key):
        command.add_argument(
            "--confirm-production",
            action="store_true",
            help="APP_ENV=production 에서 실행할 때 필요한 확인 옵션",
        )
    return parser


def read_password() -> str:
    # getpass는 숨김 입력을 못 하면 일반 입력으로 대체한다. 비밀번호가 보이지 않게 중단한다.
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        password = getpass("비밀번호: ")
        if not 1 <= len(password) <= PASSWORD_MAX_LENGTH:
            raise users.UserCommandError(
                f"비밀번호는 1~{PASSWORD_MAX_LENGTH}자여야 합니다."
            )
        if password != getpass("비밀번호 확인: "):
            raise users.UserCommandError("비밀번호 확인이 일치하지 않습니다.")
    return password


async def run_user_command(args: argparse.Namespace, password: str | None) -> None:
    async with get_sessionmaker()() as session:
        if args.command == "user-create":
            user = await users.create_user(
                session,
                email=args.email,
                name=args.name,
                user_code=args.user_code,
                password=password or "",
            )
            print(f"계정 생성 완료 (user_id={user.user_id})")
        elif args.command == "user-deactivate":
            user_id = await users.deactivate_user(session, args.email)
            print(f"계정 비활성화 및 세션 삭제 완료 (user_id={user_id})")
        elif args.command == "session-cleanup":
            count = await users.cleanup_sessions(session, now=datetime.now(UTC))
            print(f"만료 세션 {count}개 삭제 완료")


async def run_catalog_command(args: argparse.Namespace) -> None:
    async with get_sessionmaker()() as session:
        if args.command == "customer-create":
            customer = await usage_catalog.create_customer(
                session, customer_code=args.customer_code, name=args.name
            )
            print(f"고객 등록 완료 (customer_id={customer.customer_id})")
        elif args.command == "service-create":
            service = await usage_catalog.create_service(
                session,
                service_code=args.service_code,
                name=args.name,
                service_type=ServiceType(args.service_type),
            )
            print(f"서비스 등록 완료 (service_id={service.service_id})")
        elif args.command == "key-register":
            key = await usage_catalog.register_customer_key(
                session,
                display_name=args.display_name,
                secret_ref=args.secret_ref,
                customer_code=args.customer_code,
                service_code=args.service_code,
                environment=KeyEnvironment(args.environment),
            )
            print(f"Key 등록 완료 (key_id={key.key_id})")


def main(argv: list[str] | None = None) -> int:
    """명령줄 진입점. 성공하면 0, 거부되면 1을 돌려준다."""
    args = make_parser().parse_args(argv)

    try:
        ensure_command_allowed(
            current_app_env(), args.confirm_production, command=args.command
        )
        # psycopg의 async 모드는 Windows에서도 동작하도록 Selector 루프를 쓴다.
        if args.command == "seed":
            applied = asyncio.run(run_seed(), loop_factory=asyncio.SelectorEventLoop)
            print("seed 적용 완료" if applied else "이미 seed가 적용되어 있어 건너뜀")
        elif args.command in CATALOG_COMMANDS:
            asyncio.run(
                run_catalog_command(args), loop_factory=asyncio.SelectorEventLoop
            )
        else:
            # 비밀번호는 명령줄 인자 묶음(args)에 넣지 않고 숨김 입력으로만 전달한다.
            password = read_password() if args.command == "user-create" else None
            asyncio.run(
                run_user_command(args, password), loop_factory=asyncio.SelectorEventLoop
            )
    except (
        CommandRefusedError,
        users.UserCommandError,
        usage_catalog.CatalogCommandError,
    ) as error:
        print(error, file=sys.stderr)
        return 1
    except GetPassWarning, EOFError, KeyboardInterrupt:
        print("비밀번호를 안전하게 입력하지 못해 작업을 취소했습니다.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        # SQLAlchemy 예외에는 접속 정보나 SQL 파라미터(비밀번호 해시 등)가 들어갈 수 있다.
        print(
            "DB 작업에 실패했습니다. DB 연결 상태와 스키마를 확인하세요.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""운영 명령. HTTP 경로를 늘리지 않고 명령줄로만 실행한다.

사용법 (저장소 루트에서):
    uv --directory backend run python -m app.cli seed                       # 개발 DB에 mock 데이터 넣기
    uv --directory backend run python -m app.cli seed --confirm-production  # 운영(APP_ENV=production)에서만 필요
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.config import get_settings
from app.db import get_engine

SEED_FILE = Path(__file__).resolve().parents[1] / "seed" / "patron_mock_data_v0.6.sql"
PRODUCTION_ENV = "production"
# 시드가 이미 들어갔는지 알아보는 표식: 시드가 고정 ID로 넣는 첫 mock 고객
SEED_MARKER_QUERY = text(
    "SELECT EXISTS (SELECT 1 FROM customers WHERE customer_code = 'CUST-A' AND is_mock)"
)


class SeedRefusedError(Exception):
    """운영 환경에서 확인 옵션 없이 seed를 실행하려 할 때 발생한다."""


def ensure_seed_allowed(app_env: str, confirm_production: bool) -> None:
    """운영 환경이면 --confirm-production이 있을 때만 허용한다. (DB 없이 판단하는 순수 함수)"""
    if app_env == PRODUCTION_ENV and not confirm_production:
        raise SeedRefusedError(
            "APP_ENV=production 에서는 --confirm-production 옵션이 있어야 seed를 실행합니다."
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


def main(argv: list[str] | None = None) -> int:
    """명령줄 진입점. 성공하면 0, 거부되면 1을 돌려준다."""
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser(
        "seed", help="개발 DB에 mock 데이터를 넣는다 (이미 있으면 건너뜀)"
    )
    seed.add_argument(
        "--confirm-production",
        action="store_true",
        help="APP_ENV=production 에서 실행할 때 필요한 확인 옵션",
    )
    args = parser.parse_args(argv)

    try:
        ensure_seed_allowed(current_app_env(), args.confirm_production)
    except SeedRefusedError as error:
        print(error, file=sys.stderr)
        return 1

    # psycopg의 async 모드는 Windows 기본 루프(Proactor)에서 동작하지 않아 Selector 루프를 쓴다.
    applied = asyncio.run(run_seed(), loop_factory=asyncio.SelectorEventLoop)
    print("seed 적용 완료" if applied else "이미 seed가 적용되어 있어 건너뜀")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

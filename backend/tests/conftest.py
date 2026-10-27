"""공통 테스트 fixture. DB가 필요한 테스트는 patron_test DB에서만 돌린다.

흐름:
1. test_database_url: .env의 TEST_DATABASE_URL을 읽고, patron_test가 아니면 거부한다.
2. migrated_database: 테스트 시작 시 한 번, 마이그레이션으로 patron_test에 테이블을 만든다.
3. db_session: 테스트마다 트랜잭션을 열고, 테스트가 끝나면 롤백해 흔적을 남기지 않는다.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from tests.db_helpers import Factory

# 테스트가 접속해도 되는 유일한 DB 이름. 개발 DB(patron)를 실수로 지우지 않기 위한 안전장치다.
TEST_DATABASE_NAME = "patron_test"
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    """async 테스트를 Selector 루프에서 돌린다(pytest-asyncio 훅).

    psycopg의 async 모드는 Windows 기본 루프(ProactorEventLoop)에서 동작하지 않는다.
    """
    return {"selector": asyncio.SelectorEventLoop}


def require_test_database_url(raw_url: str | None) -> URL:
    """URL이 patron_test를 가리킬 때만 URL 객체로 돌려주고, 아니면 테스트를 멈춘다.

    문자열 대신 URL 객체를 돌려주는 이유: pytest가 실패 출력에 fixture 값을 그대로 보여 주는데,
    URL 객체는 비밀번호를 ***로 가려서 보여 준다. 오류 메시지에도 DB 이름만 넣는다.
    """
    if raw_url is None or not raw_url.strip():
        raise RuntimeError(
            "TEST_DATABASE_URL이 비어 있습니다. .env에 patron_test 접속 URL을 넣으세요."
        )
    url = make_url(raw_url)
    if url.database != TEST_DATABASE_NAME:
        raise RuntimeError(
            f"TEST_DATABASE_URL이 {TEST_DATABASE_NAME}가 아닌 DB({url.database})를 가리킵니다."
        )
    return url


def make_alembic_config(database_url: URL) -> Config:
    """alembic.ini를 읽되, 접속 URL은 넘겨받은 값(patron_test)으로 바꾼 Alembic 설정을 만든다.

    env.py는 URL이 이미 들어 있으면 .env의 DATABASE_URL(개발 DB)을 쓰지 않는다.
    """
    config = Config(str(ALEMBIC_INI))
    raw_url = database_url.render_as_string(hide_password=False)
    # alembic 설정 형식에서 %는 특수문자라 %%로 바꿔 넘긴다.
    config.set_main_option("sqlalchemy.url", raw_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    """검사를 통과한 patron_test 접속 URL. 테스트 실행 전체에서 한 번만 확인한다."""
    secret = get_settings().test_database_url
    return require_test_database_url(secret.get_secret_value() if secret else None)


@pytest.fixture(scope="session")
def alembic_config(test_database_url: URL) -> Config:
    """patron_test를 대상으로 하는 Alembic 설정."""
    return make_alembic_config(test_database_url)


@pytest.fixture(scope="session")
def migrated_database(alembic_config: Config, test_database_url: URL) -> URL:
    """patron_test를 비운 뒤 최신 마이그레이션까지 적용하고, 그 접속 URL을 돌려준다.

    create_all 대신 마이그레이션을 쓰는 이유: 마이그레이션 파일 자체가 검증되기 때문이다.
    """
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    return test_database_url


@pytest.fixture
async def db_session(migrated_database: URL) -> AsyncIterator[AsyncSession]:
    """테스트 하나에 쓸 세션. 테스트가 끝나면 모든 변경을 롤백한다.

    바깥 트랜잭션을 먼저 열고 세션을 그 안에 묶는다. 테스트 코드가 commit해도
    실제로는 savepoint만 확정되고, 마지막에 바깥 트랜잭션을 롤백하면 모두 사라진다.
    """
    engine = create_async_engine(migrated_database, poolclass=NullPool)
    async with engine.connect() as connection:
        outer_transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await outer_transaction.rollback()
    await engine.dispose()


@pytest.fixture
def factory(db_session: AsyncSession) -> Factory:
    """테스트 행 생성기. db_session 안에서 만들므로 테스트가 끝나면 함께 롤백된다."""
    return Factory(db_session)

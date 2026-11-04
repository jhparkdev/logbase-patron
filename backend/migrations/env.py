import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.models import Base

# 현재 사용하는 .ini 파일의 설정값에 접근하는 Alembic Config 객체다.
config = context.config

# 설정 파일의 로깅 설정을 읽어 Python 로거를 구성한다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# 접속 URL 정하기: alembic.ini의 sqlalchemy.url은 비어 있다.
# 테스트처럼 호출하는 쪽이 URL을 직접 넘겼으면(patron_test 등) 그 값을 그대로 쓰고,
# 아니면 앱 설정의 DATABASE_URL(개발 DB)을 쓴다.
if not config.get_main_option("sqlalchemy.url"):
    database_url = get_settings().database_url.get_secret_value()
    # alembic 설정 파일 형식에서 %는 특수문자라, 비밀번호에 %가 있으면 %%로 바꿔 넘긴다.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# autogenerate에서 사용할 모델의 메타데이터를 지정한다.
# 모델을 별도 모듈에서 불러오는 경우의 예:
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# autogenerate와 alembic check는 app/models.py의 모델(Base.metadata)과 실제 DB를 비교한다.
target_metadata = Base.metadata

# env.py에 필요한 추가 설정도 아래와 같이 읽을 수 있다.
# my_important_option = config.get_main_option("my_important_option")
# 필요한 설정에 따라 위 예시를 확장한다.


def run_migrations_offline() -> None:
    """DB에 연결하지 않는 오프라인 모드로 마이그레이션 SQL을 생성한다.

    엔진 대신 접속 URL만으로 실행 컨텍스트를 설정하므로 DBAPI 드라이버도 필요 없다.
    이 모드에서 context.execute()에 전달한 SQL은 DB에서 실행하지 않고 스크립트로 출력한다.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 엔진을 만들고 DB 연결을 마이그레이션 실행 컨텍스트에 전달한다."""

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """DB에 연결하는 온라인 모드로 마이그레이션을 실행한다."""

    # psycopg의 async 모드는 Windows 기본 루프(ProactorEventLoop)에서 동작하지 않아
    # Selector 루프를 쓴다. Linux·macOS는 원래 Selector 계열이라 동작이 같다.
    asyncio.run(run_async_migrations(), loop_factory=asyncio.SelectorEventLoop)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

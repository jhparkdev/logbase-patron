import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 접속 URL 정하기: alembic.ini의 sqlalchemy.url은 비어 있다.
# 테스트처럼 호출하는 쪽이 URL을 직접 넘겼으면(patron_test 등) 그 값을 그대로 쓰고,
# 아니면 앱 설정의 DATABASE_URL(개발 DB)을 쓴다.
if not config.get_main_option("sqlalchemy.url"):
    database_url = get_settings().database_url.get_secret_value()
    # alembic 설정 파일 형식에서 %는 특수문자라, 비밀번호에 %가 있으면 %%로 바꿔 넘긴다.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# app/models.py를 만들 때 Base.metadata로 연결한다. 그전까지 autogenerate는 비교할 모델이 없다.
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

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
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # psycopg의 async 모드는 Windows 기본 루프(ProactorEventLoop)에서 동작하지 않아
    # Selector 루프를 쓴다. Linux·macOS는 원래 Selector 계열이라 동작이 같다.
    asyncio.run(run_async_migrations(), loop_factory=asyncio.SelectorEventLoop)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

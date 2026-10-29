"""DB 연결. 엔진은 프로세스에 하나만 만들고, 요청마다 세션을 하나씩 열어 준다.

- 엔진: DB 접속을 관리하는 객체. 내부에 접속 풀(pool)을 두고 재사용한다.
- 세션: 쿼리와 트랜잭션(commit/rollback)을 다루는 작업 단위. 요청 하나에 하나를 쓴다.
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """설정의 DATABASE_URL로 async 엔진을 처음 한 번만 만들고, 이후에는 같은 엔진을 돌려준다.

    만들 때는 접속하지 않고, 처음 쿼리를 보낼 때 접속한다.
    """
    return create_async_engine(get_settings().database_url.get_secret_value())


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """세션을 찍어 내는 생성기를 한 번만 만든다.

    expire_on_commit=False: commit 뒤에도 객체 값을 그대로 읽을 수 있게 한다.
    async에서는 만료된 값을 다시 읽으려 하면 오류가 나기 때문이다.
    """
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성. 요청이 시작되면 세션을 열어 넘기고, 요청이 끝나면 닫는다."""
    async with get_sessionmaker()() as session:
        yield session


# 라우터에서 `session: SessionDep`처럼 쓰면 FastAPI가 get_session으로 세션을 넣어 준다.
SessionDep = Annotated[AsyncSession, Depends(get_session)]

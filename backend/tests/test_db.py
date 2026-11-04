"""app/db.py 테스트. 실제 DB에는 접속하지 않고 엔진·세션 설정만 확인한다.

(엔진과 세션은 만들 때 접속하지 않고, 처음 쿼리를 보낼 때 접속한다.)
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.config import get_settings

# 테스트용 가짜 URL. 접속하지 않으므로 실제 비밀번호가 필요 없다.
DEV_URL = "postgresql+psycopg://patron:dev-secret@localhost:5432/patron"


def _clear_caches() -> None:
    """한 번 만들어 저장해 둔 설정·엔진·세션 생성기를 지워, 다음 호출 때 새로 만들게 한다."""
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()


@pytest.fixture(autouse=True)
def dev_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """모든 테스트 전에 가짜 DATABASE_URL을 넣고, 테스트 앞뒤로 캐시를 비운다.

    autouse=True라서 이 파일의 모든 테스트에 자동으로 적용된다.
    """
    monkeypatch.setenv("DATABASE_URL", DEV_URL)
    _clear_caches()
    yield
    _clear_caches()


def test_engine_is_created_once_from_settings_url() -> None:
    """엔진은 프로세스에 하나만 만들어지고, 설정의 DATABASE_URL을 쓴다."""
    engine = db.get_engine()

    assert db.get_engine() is engine
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.database == "patron"


def test_sessions_do_not_expire_on_commit() -> None:
    """commit 뒤에도 객체 값을 읽을 수 있게 expire_on_commit=False로 만든다.

    async에서는 만료된 값을 다시 읽으려다 오류가 나기 때문이다.
    """
    assert db.get_sessionmaker().kw["expire_on_commit"] is False


async def test_get_session_yields_async_session() -> None:
    """FastAPI 의존성 get_session이 요청 하나에 쓸 AsyncSession을 넘겨준다."""
    sessions = db.get_session()

    session = await anext(sessions)

    assert isinstance(session, AsyncSession)
    # 요청이 끝난 것처럼 마무리해 세션을 닫는다.
    await sessions.aclose()

"""tests/conftest.py의 안전장치와 롤백 격리를 검증한다."""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.conftest import require_test_database_url

URL_BASE = "postgresql+psycopg://patron:dev-secret@127.0.0.1:5432"


def test_accepts_patron_test_url() -> None:
    """patron_test를 가리키는 URL은 통과한다."""
    url = require_test_database_url(f"{URL_BASE}/patron_test")

    assert url.database == "patron_test"
    assert url.password == "dev-secret"


def test_accepted_url_hides_password_when_printed() -> None:
    """돌려준 URL을 출력하거나 테스트 실패 메시지에 나와도 비밀번호가 보이지 않는다."""
    url = require_test_database_url(f"{URL_BASE}/patron_test")

    assert "dev-secret" not in repr(url)
    assert "dev-secret" not in str(url)


@pytest.mark.parametrize(
    "database_name",
    # 개발 DB, 이름이 비슷한 DB, 기본 DB를 모두 거부해야 한다.
    ["patron", "patron_test_old", "postgres"],
)
def test_rejects_other_databases(database_name: str) -> None:
    """patron_test가 아닌 DB를 가리키면 거부하고, 오류에 비밀번호를 드러내지 않는다."""
    with pytest.raises(RuntimeError) as error:
        require_test_database_url(f"{URL_BASE}/{database_name}")

    assert "dev-secret" not in str(error.value)


@pytest.mark.parametrize("raw_url", [None, "", "   "])
def test_rejects_missing_url(raw_url: str | None) -> None:
    """TEST_DATABASE_URL이 없거나 비어 있으면 거부한다."""
    with pytest.raises(RuntimeError):
        require_test_database_url(raw_url)


async def test_db_session_uses_patron_test(db_session: AsyncSession) -> None:
    """db_session은 patron_test에 접속한다."""
    result = await db_session.execute(text("SELECT current_database()"))

    assert result.scalar_one() == "patron_test"


async def test_db_session_commit_is_not_visible_outside(
    db_session: AsyncSession, migrated_database: URL
) -> None:
    """테스트 안에서 commit해도 다른 접속에서는 보이지 않는다(끝나면 롤백되므로)."""
    await db_session.execute(text("CREATE TABLE rollback_probe (id integer)"))
    await db_session.commit()

    other_engine = create_async_engine(migrated_database, poolclass=NullPool)
    async with other_engine.connect() as other:
        # to_regclass: 테이블이 없으면 NULL을 돌려준다.
        found = await other.scalar(text("SELECT to_regclass('rollback_probe')"))
    await other_engine.dispose()

    assert found is None

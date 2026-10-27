"""TEST_DATABASE_URL이 patron_test를 가리키고 실제로 접속되는지 확인한다(backend/CLAUDE.md 테스트 절)."""

import os

import psycopg


def test_connects_to_patron_test_database() -> None:
    # psycopg는 SQLAlchemy 접두어(postgresql+psycopg://)를 모르므로 바꿔서 연결한다.
    conninfo = os.environ["TEST_DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    with psycopg.connect(conninfo) as conn:
        assert conn.execute("SELECT current_database()").fetchone() == ("patron_test",)

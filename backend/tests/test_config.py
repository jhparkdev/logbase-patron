"""app/config.py 테스트. 실제 .env 대신 테스트가 정한 환경변수·임시 파일만 읽게 한다."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

# 테스트용 가짜 값. 실제 비밀번호가 아니며, 화면에 드러나는지 찾을 표식으로 쓴다.
DEV_URL = "postgresql+psycopg://patron:dev-secret@localhost:5432/patron"
TEST_URL = "postgresql+psycopg://patron:dev-secret@localhost:5432/patron_test"


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """PC에 설정된 DB 환경변수를 테스트 동안만 지워, 테스트가 넣은 값만 보이게 한다.

    monkeypatch로 바꾼 값은 테스트가 끝나면 자동으로 원래대로 돌아온다.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    return monkeypatch


def test_reads_database_url_from_environment(clean_env: pytest.MonkeyPatch) -> None:
    """DATABASE_URL 환경변수가 database_url 필드로 들어온다."""
    clean_env.setenv("DATABASE_URL", DEV_URL)

    # _env_file=None: 실제 .env 파일은 읽지 않는다.
    settings = Settings(_env_file=None)

    assert settings.database_url.get_secret_value() == DEV_URL


def test_missing_database_url_is_rejected(clean_env: pytest.MonkeyPatch) -> None:
    """필수 값인 DATABASE_URL이 없으면 설정을 만들 수 없다."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_test_database_url_is_optional(clean_env: pytest.MonkeyPatch) -> None:
    """TEST_DATABASE_URL은 없으면 None이고, 있으면 그 값을 읽는다."""
    clean_env.setenv("DATABASE_URL", DEV_URL)

    assert Settings(_env_file=None).test_database_url is None

    clean_env.setenv("TEST_DATABASE_URL", TEST_URL)

    assert Settings(_env_file=None).test_database_url.get_secret_value() == TEST_URL


def test_unrelated_keys_in_env_file_are_ignored(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """.env에 설정과 관계없는 키(POSTGRES_PASSWORD 등)가 있어도 오류가 나지 않는다."""
    # tmp_path: pytest가 테스트마다 만들고 지워 주는 임시 폴더
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"DATABASE_URL={DEV_URL}\nPOSTGRES_PASSWORD=dev-secret\n", encoding="utf-8"
    )

    settings = Settings(_env_file=env_file)

    assert settings.database_url.get_secret_value() == DEV_URL


def test_database_password_is_hidden_in_repr(clean_env: pytest.MonkeyPatch) -> None:
    """설정 객체를 출력하거나 로그에 남겨도 DB 비밀번호가 보이지 않는다."""
    clean_env.setenv("DATABASE_URL", DEV_URL)
    clean_env.setenv("TEST_DATABASE_URL", TEST_URL)

    settings = Settings(_env_file=None)

    assert "dev-secret" not in repr(settings)
    assert "dev-secret" not in str(settings)

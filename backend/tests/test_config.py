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
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGIN", raising=False)
    return monkeypatch


def test_app_env_defaults_to_development(clean_env: pytest.MonkeyPatch) -> None:
    """APP_ENV가 없으면 개발 환경으로 본다(운영 보호 장치가 운영에서만 걸리도록)."""
    clean_env.setenv("DATABASE_URL", DEV_URL)

    assert Settings(_env_file=None).app_env == "development"


def test_reads_app_env_from_environment(clean_env: pytest.MonkeyPatch) -> None:
    """APP_ENV 환경변수가 app_env 필드로 들어온다."""
    clean_env.setenv("DATABASE_URL", DEV_URL)
    clean_env.setenv("APP_ENV", "production")

    assert Settings(_env_file=None).app_env == "production"


def test_session_cookie_is_secure_by_default(clean_env: pytest.MonkeyPatch) -> None:
    """설정을 빠뜨린 배포 환경에서도 세션 쿠키가 HTTPS로만 전송되게 기본값은 켬이다."""
    clean_env.setenv("DATABASE_URL", DEV_URL)

    assert Settings(_env_file=None).session_cookie_secure is True


def test_session_cookie_secure_can_be_turned_off(
    clean_env: pytest.MonkeyPatch,
) -> None:
    """http로 띄우는 로컬 개발 환경에서는 끌 수 있다."""
    clean_env.setenv("DATABASE_URL", DEV_URL)
    clean_env.setenv("SESSION_COOKIE_SECURE", "false")

    assert Settings(_env_file=None).session_cookie_secure is False


def test_allowed_origin_is_empty_by_default(clean_env: pytest.MonkeyPatch) -> None:
    """값이 없으면 None이다. 이때 상태를 바꾸는 요청은 모두 거절된다(app/api/deps.py)."""
    clean_env.setenv("DATABASE_URL", DEV_URL)

    assert Settings(_env_file=None).allowed_origin is None


def test_reads_allowed_origin_from_environment(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("DATABASE_URL", DEV_URL)
    clean_env.setenv("ALLOWED_ORIGIN", "http://localhost:5173")

    assert Settings(_env_file=None).allowed_origin == "http://localhost:5173"


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

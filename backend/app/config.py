"""앱 설정. 환경변수(와 로컬 .env 파일)는 이 모듈 한 곳에서만 읽는다."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# 명령을 저장소 루트와 backend/ 어디서 실행해도 루트의 .env를 읽게 한다.
# (이 파일 위치 backend/app/config.py에서 두 단계 위가 저장소 루트)
# 배포 환경에는 이 파일이 없고 환경변수만 있다.
ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """환경변수를 읽어 타입을 검사한 설정 값 묶음.

    필드 이름은 같은 이름의 환경변수와 연결된다(대소문자 무시).
    예: database_url ← DATABASE_URL. 필수 값이 없으면 만들 때 오류가 난다.
    값을 찾는 순서는 실제 환경변수가 먼저이고, 없으면 .env 파일이다.
    """

    # .env에는 docker compose용 POSTGRES_* 등 다른 키도 있으므로 모르는 키는 무시한다.
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, extra="ignore")

    # 접속 URL에 비밀번호가 들어 있어 repr과 로그에 드러나지 않게 SecretStr로 받는다.
    # 실제 값이 필요할 때만 .get_secret_value()로 꺼낸다.
    # 개발·운영 DB (필수)
    database_url: SecretStr
    # 테스트 전용 patron_test DB (테스트에서만 사용)
    test_database_url: SecretStr | None = None
    # 실행 환경 이름. "production"이면 seed 같은 위험한 명령에 확인 옵션을 요구한다.
    app_env: str = "development"
    # 세션 쿠키를 HTTPS에서만 보낸다. dev·운영 배포 모두 HTTPS라 기본값은 켬이고,
    # http로 띄우는 로컬 개발에서만 .env에 SESSION_COOKIE_SECURE=false로 끈다.
    session_cookie_secure: bool = True
    # 상태를 바꾸는 요청(POST 등)을 받을 화면 주소. 예: http://localhost:5173 (끝에 / 없음)
    # 비어 있으면 그런 요청을 모두 거절한다.
    allowed_origin: str | None = None


@lru_cache
def get_settings() -> Settings:
    """설정을 처음 한 번만 읽고, 이후에는 같은 객체를 돌려준다.

    모듈을 import할 때가 아니라 처음 호출할 때 읽으므로, 테스트에서 환경변수를 바꾼 뒤
    get_settings.cache_clear()로 다시 읽게 할 수 있다.
    """
    return Settings()

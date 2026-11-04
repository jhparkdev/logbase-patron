"""앱 설정. 환경변수(와 로컬 .env 파일)는 이 모듈 한 곳에서만 읽는다."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# 명령을 저장소 루트와 backend/ 어디서 실행해도 루트의 .env를 읽게 한다.
# (이 파일 위치 backend/app/config.py에서 두 단계 위가 저장소 루트)
# 배포 환경에는 이 파일이 없고 환경변수만 있다.
ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# 개발에서 업로드 이미지를 두는 기본 폴더. 저장소 밖에 두어 실수로 커밋되지 않게 하고,
# 프로젝트 폴더를 지우거나 다시 받아도 입력 이력이 가리키는 파일이 사라지지 않게 한다
DEFAULT_IMAGE_STORAGE_DIR = Path.home() / ".patron-uploads"


class Settings(BaseSettings):
    """환경변수를 읽어 타입을 검사한 설정 값 묶음.

    필드 이름은 같은 이름의 환경변수와 연결된다(대소문자 무시).
    예: database_url ← DATABASE_URL. 필수 값이 없으면 만들 때 오류가 난다.
    값을 찾는 순서는 실제 환경변수가 먼저이고, 없으면 .env 파일이다.
    """

    # .env에는 docker compose용 POSTGRES_* 등 다른 키도 있으므로 모르는 키는 무시한다.
    # 값이 잘못되었을 때 시작 오류에 입력한 값(Key, 접속 URL의 비밀번호)이 찍히지 않게 한다.
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE, extra="ignore", hide_input_in_errors=True
    )

    # 접속 URL에 비밀번호가 들어 있어 repr과 로그에 드러나지 않게 SecretStr로 받는다.
    # 실제 값이 필요할 때만 .get_secret_value()로 꺼낸다.
    # 개발·운영 DB (필수)
    database_url: SecretStr
    # 테스트 전용 patron_test DB (테스트에서만 사용)
    test_database_url: SecretStr | None = None
    # 실행 환경 이름. "production"이면 seed 같은 위험한 명령에 확인 옵션을 요구한다.
    # 계정 생성·비활성화·만료 세션 정리 CLI에도 같은 운영 보호 규칙을 적용한다.
    app_env: str = "development"
    # 세션 쿠키를 HTTPS에서만 보낸다. dev·운영 배포 모두 HTTPS라 기본값은 켬이고,
    # http로 띄우는 로컬 개발에서만 .env에 SESSION_COOKIE_SECURE=false로 끈다.
    session_cookie_secure: bool = True
    # 상태를 바꾸는 요청(POST 등)을 받을 화면 주소. 예: http://localhost:5173 (끝에 / 없음)
    # 비어 있으면 그런 요청을 모두 거절한다.
    allowed_origin: str | None = None
    # OpenRouter Key 원문. 로컬에서는 작업할 때만 넣고 끝나면 지우므로 없어도 앱은 뜬다.
    # 없으면 비교 실행 접수만 거절한다(app/api/simulation_deps.py).
    openrouter_api_key: SecretStr | None = None
    # 로컬 에이전트 실험은 명시적으로 켠 환경에서만 제공한다.
    assistant_enabled: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_context_length: int = Field(default=8192, ge=4096, le=32768)
    # 구성원별 Command Code Key 원문. DB의 secret_ref → Key 원문을 JSON 한 줄로 받는다.
    # 예: COMMAND_CODE_API_KEYS={"COMMAND_CODE_KEY_HONG": "..."}. 비어 있어도 앱은 뜨고,
    # Key가 없는 구성원은 사용량 표에서 "Key 없음"으로 보인다. JSON이 깨졌으면 시작할 때 멈춘다.
    # NoDecode: 값이 비어 있어도(.env.example를 복사한 상태) 설정을 읽다 멈추지 않게 아래에서 직접 읽는다.
    command_code_api_keys: Annotated[dict[str, SecretStr], NoDecode] = Field(
        default_factory=dict
    )
    # 시뮬레이터 이미지를 두는 로컬 폴더. 개발용이다(Cloud Run 의 디스크는 임시라서 배포에서는
    # 아래 GCS 버킷을 쓴다). DB 에는 이 폴더 안의 상대 경로와 해시만 남는다.
    image_storage_dir: Path = DEFAULT_IMAGE_STORAGE_DIR
    # 시뮬레이터 이미지를 둘 GCS 버킷 이름. 있으면 로컬 폴더 대신 이 버킷을 쓴다.
    # 인증은 Cloud Run 서비스 계정의 기본 자격증명이라 키 값은 받지 않는다.
    image_storage_bucket: str | None = None

    @field_validator("command_code_api_keys", mode="before")
    @classmethod
    def _read_command_code_api_keys(cls, value: object) -> object:
        """환경변수의 JSON 글자를 읽는다. 비어 있으면 Key 없음이고, 깨진 JSON은 오류로 멈춘다."""
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value


@lru_cache
def get_settings() -> Settings:
    """설정을 처음 한 번만 읽고, 이후에는 같은 객체를 돌려준다.

    모듈을 import할 때가 아니라 처음 호출할 때 읽으므로, 테스트에서 환경변수를 바꾼 뒤
    get_settings.cache_clear()로 다시 읽게 할 수 있다.
    """
    return Settings()

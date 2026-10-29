"""로그인·현재 사용자 요청·응답 모델."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr

# 이메일 주소 최대 길이(RFC 5321 경로 제한)
EMAIL_MAX_LENGTH = 254
# Argon2는 입력 길이만큼 오래 계산하므로, 아주 긴 입력으로 서버를 붙잡지 못하게 막는다.
PASSWORD_MAX_LENGTH = 128


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=EMAIL_MAX_LENGTH)
    # SecretStr: 모델을 출력하거나 로그에 남겨도 비밀번호가 보이지 않는다.
    password: SecretStr = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class CurrentUserRead(BaseModel):
    """로그인한 관리자. 비밀번호 해시와 세션 값은 내보내지 않는다."""

    # ORM 사용자 객체에서 아래 필드만 읽는다. 모델에 다른 속성이 있어도 응답에는 포함되지 않는다.
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_code: str
    name: str
    email: str

"""비밀번호 해시, 세션 토큰, 세션 만료 판단. DB 없이 호출할 수 있는 함수만 둔다.

- 비밀번호: pwdlib의 Argon2id 해시만 저장한다. 원문은 저장하거나 로그에 남기지 않는다.
- 세션 토큰: 원문은 쿠키로만 보내고, DB에는 SHA-256 해시(소문자 16진수 64자)만 둔다.
- Argon2 계산은 CPU를 오래 쓰는 동기 함수다. async 경로에서는 스레드에서 실행해야 한다.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from pwdlib import PasswordHash

# 세션 토큰 수명. 쿠키 수명도 이 값에서 계산한다.
SESSION_TTL = timedelta(hours=12)
SESSION_TOKEN_BYTES = 32

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    # 매번 새 솔트가 붙으므로 같은 비밀번호도 서로 다른 해시로 저장된다.
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


# 계정이 없을 때 대신 검증할 해시. 실제 계정과 같은 설정으로 만들어야 검증 시간이 같다.
# 원문은 아무도 모르는 임의값이라 어떤 비밀번호로도 통과하지 않는다.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(SESSION_TOKEN_BYTES))


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    """계정이 없으면(None) 더미 해시로 한 번 검증하고 False를 돌려준다.

    계정 유무와 관계없이 Argon2 검증을 꼭 한 번 해서, 응답 시간으로 계정 존재 여부가 드러나지 않게 한다.
    """
    if password_hash is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return False
    return verify_password(password, password_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """DB에 저장하고 조회할 때 쓰는 토큰 해시. 소문자 16진수 64자."""
    return hashlib.sha256(token.encode()).hexdigest()


def session_expires_at(issued_at: datetime) -> datetime:
    return issued_at + SESSION_TTL


def is_session_valid(
    *, expires_at: datetime, user_is_active: bool, now: datetime
) -> bool:
    """만료 시각이 지나지 않았고 사용자가 활성 상태일 때만 유효하다. 만료 시각과 같으면 만료다."""
    return user_is_active and now < expires_at

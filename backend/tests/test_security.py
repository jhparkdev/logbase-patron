"""app/security.py 테스트. DB 없이 비밀번호 해시, 세션 토큰, 만료 판단을 확인한다."""

import re
from datetime import timedelta

import pytest

from app import security
from tests.db_helpers import T0

# seed(patron_mock_data_v0.6.sql)의 admin1 해시와 개발용 비밀번호
SEED_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$gaRyHd/7tmr/juCD6muBAg$HsHckDxel4IYHkYqpMinwJOmBAhInt2fQM+WEI7bexg"
SEED_PASSWORD = "patron-dev-1234"
LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
URL_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")
# 32바이트를 base64url(패딩 없음)로 쓰면 43자다.
TOKEN_32_BYTES_LENGTH = 43
ONE_MICROSECOND = timedelta(microseconds=1)


def argon2_parameters(password_hash: str) -> str:
    """'$argon2id$v=19$m=65536,t=3,p=4$...'에서 알고리즘·버전·비용 설정 부분만 꺼낸다."""
    return "$".join(password_hash.split("$")[:4])


# 비밀번호


def test_password_is_stored_as_argon2id_hash() -> None:
    password_hash = security.hash_password(SEED_PASSWORD)

    assert password_hash.startswith("$argon2id$")
    assert SEED_PASSWORD not in password_hash


def test_same_password_gets_different_hashes() -> None:
    """솔트가 매번 달라 같은 비밀번호라도 해시가 다르다."""
    assert security.hash_password(SEED_PASSWORD) != security.hash_password(
        SEED_PASSWORD
    )


def test_verify_password_accepts_only_the_right_password() -> None:
    password_hash = security.hash_password(SEED_PASSWORD)

    assert security.verify_password(SEED_PASSWORD, password_hash)
    assert not security.verify_password("wrong-password", password_hash)


def test_seed_admin_hash_is_compatible() -> None:
    assert security.verify_password(SEED_PASSWORD, SEED_PASSWORD_HASH)


def test_new_hash_uses_same_settings_as_seed() -> None:
    """설정이 다르면 계산 시간이 달라져 응답 시간으로 계정 유무가 드러날 수 있다."""
    assert argon2_parameters(security.hash_password("x")) == argon2_parameters(
        SEED_PASSWORD_HASH
    )


# 계정이 없을 때의 더미 검증


def test_missing_account_still_runs_one_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_hashes: list[str] = []
    real_verify = security.verify_password

    def spy(password: str, password_hash: str) -> bool:
        verified_hashes.append(password_hash)
        return real_verify(password, password_hash)

    monkeypatch.setattr(security, "verify_password", spy)

    assert security.verify_password_or_dummy(SEED_PASSWORD, None) is False
    assert len(verified_hashes) == 1
    assert argon2_parameters(verified_hashes[0]) == argon2_parameters(
        SEED_PASSWORD_HASH
    )


def test_existing_account_is_verified_with_its_hash() -> None:
    assert security.verify_password_or_dummy(SEED_PASSWORD, SEED_PASSWORD_HASH)
    assert not security.verify_password_or_dummy("wrong-password", SEED_PASSWORD_HASH)


# 세션 토큰


def test_session_token_is_32_random_bytes_url_safe() -> None:
    token = security.new_session_token()

    assert len(token) == TOKEN_32_BYTES_LENGTH
    assert URL_SAFE.match(token)
    assert security.new_session_token() != token


def test_session_token_hash_is_lowercase_sha256_hex() -> None:
    """DB CHECK(token_hash ~ '^[0-9a-f]{64}$')를 통과하는 형식이어야 한다."""
    token = security.new_session_token()
    token_hash = security.hash_session_token(token)

    assert LOWER_HEX_SHA256.match(token_hash)
    assert token not in token_hash
    assert security.hash_session_token(token) == token_hash


def test_session_token_hash_is_sha256() -> None:
    # SHA-256("abc") 표준 테스트 값
    assert (
        security.hash_session_token("abc")
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


# 세션 만료


def test_session_lasts_12_hours() -> None:
    assert security.SESSION_TTL == timedelta(hours=12)
    assert security.session_expires_at(T0) == T0 + timedelta(hours=12)


@pytest.mark.parametrize(
    ("now_offset", "expected"),
    [
        (-ONE_MICROSECOND, True),  # 만료 바로 전
        (timedelta(0), False),  # 정확히 만료 시각
        (ONE_MICROSECOND, False),  # 만료 바로 후
    ],
)
def test_session_is_valid_only_before_expiry(
    now_offset: timedelta, expected: bool
) -> None:
    expires_at = security.session_expires_at(T0)

    assert (
        security.is_session_valid(
            expires_at=expires_at, user_is_active=True, now=expires_at + now_offset
        )
        is expected
    )


def test_session_of_inactive_user_is_invalid() -> None:
    assert not security.is_session_valid(
        expires_at=security.session_expires_at(T0), user_is_active=False, now=T0
    )

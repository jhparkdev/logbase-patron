"""결정적 식별자. 같은 난수 시드면 같은 값을 만든다.

호출·작업 ID는 실제 서비스처럼 시각이 앞에 오는 UUIDv7로 만든다. 표준 라이브러리의 uuid7()은
현재 시각을 쓰므로, 지정한 시각과 시드 난수로 직접 조립한다(RFC 9562 배치).
"""

import hashlib
import string
import uuid
from datetime import datetime
from random import Random

# 이 값을 바꾸면 모든 mock 행과 기대 합계가 바뀐다. 데이터를 다시 만들 의도가 있을 때만 바꾼다.
SEED = "logbase-patron-mock-v1"
MS_PER_SECOND = 1000
TIMESTAMP_BITS = 48
RAND_A_BITS = 12
RAND_B_BITS = 62
UUID_VERSION_7 = 0x7
RFC_4122_VARIANT = 0b10
GENERATION_SUFFIX_LENGTH = 20
GENERATION_ALPHABET = string.ascii_letters + string.digits


def rng_for(stream: str) -> Random:
    """생성 단계마다 따로 쓰는 난수. 문자열 시드는 실행 환경과 관계없이 같은 수열을 만든다."""
    return Random(f"{SEED}:{stream}")


def uuid7_at(at: datetime, rng: Random) -> uuid.UUID:
    millis = int(at.timestamp() * MS_PER_SECOND) & ((1 << TIMESTAMP_BITS) - 1)
    value = (
        millis << 80
        | UUID_VERSION_7 << 76
        | rng.getrandbits(RAND_A_BITS) << 64
        | RFC_4122_VARIANT << 62
        | rng.getrandbits(RAND_B_BITS)
    )
    return uuid.UUID(int=value)


def generation_id(at: datetime, rng: Random) -> str:
    """OpenRouter generation ID 모양(gen-<Unix 초>-<영숫자 20자>)."""
    suffix = "".join(rng.choices(GENERATION_ALPHABET, k=GENERATION_SUFFIX_LENGTH))
    return f"gen-{int(at.timestamp())}-{suffix}"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

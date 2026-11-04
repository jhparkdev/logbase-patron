"""app/mock_data/ids.py 테스트: 시각을 담은 결정적 UUIDv7과 생성 ID."""

from datetime import UTC, datetime, timedelta
from random import Random

from app.mock_data import ids

AT = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
UUID_VERSION_7 = 7
MS_PER_SECOND = 1000


def test_uuid7_records_the_given_time_in_milliseconds() -> None:
    value = ids.uuid7_at(AT, Random(1))

    assert value.version == UUID_VERSION_7
    assert value.int >> 80 == int(AT.timestamp() * MS_PER_SECOND)


def test_same_seed_gives_the_same_ids() -> None:
    assert ids.uuid7_at(AT, Random(1)) == ids.uuid7_at(AT, Random(1))
    assert ids.generation_id(AT, Random(1)) == ids.generation_id(AT, Random(1))


def test_later_time_sorts_after_earlier_time() -> None:
    rng = Random(1)
    earlier = ids.uuid7_at(AT, rng)
    later = ids.uuid7_at(AT + timedelta(milliseconds=1), rng)

    assert earlier < later


def test_generation_id_starts_with_the_unix_second() -> None:
    value = ids.generation_id(AT, Random(1))

    assert value.startswith(f"gen-{int(AT.timestamp())}-")


def test_sha256_hex_is_64_lowercase_hex_chars() -> None:
    value = ids.sha256_hex("입력")

    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)

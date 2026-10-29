"""app/api/deps.py 테스트."""

from datetime import UTC, datetime

from app.api.deps import get_now


def test_now_is_current_utc_time() -> None:
    """시각 비교와 DB 저장이 어긋나지 않도록 UTC 기준의 aware datetime을 돌려준다."""
    before = datetime.now(UTC)
    now = get_now()
    after = datetime.now(UTC)

    assert now.tzinfo is UTC
    assert before <= now <= after

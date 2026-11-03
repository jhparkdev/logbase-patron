"""Mock 데이터가 다루는 기간. 일정은 KST로 정하고, DB에는 timestamptz로 들어간다."""

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")
MOCK_YEAR = 2026

# 3개월 추세와 이번 달(11월 초)을 함께 보여 주는 기간.
# 시연일(2026-11-06) 화면에 미래 시각이 보이지 않도록 그 뒤의 행은 만들지 않는다.
PERIOD_START = datetime(MOCK_YEAR, 8, 1, tzinfo=KST)
PERIOD_END = datetime(MOCK_YEAR, 11, 6, 9, 0, tzinfo=KST)


def kst(month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """MOCK_YEAR의 KST 시각."""
    return datetime(MOCK_YEAR, month, day, hour, minute, tzinfo=KST)

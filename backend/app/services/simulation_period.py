from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

DEFAULT_PERIOD_DAYS = 30
MAX_PERIOD_DAYS = 366


class InvalidPeriodReason(StrEnum):
    INCOMPLETE = "INCOMPLETE"
    START_AFTER_END = "START_AFTER_END"
    TOO_LONG = "TOO_LONG"


@dataclass(frozen=True)
class DateRange:
    """KST 달력 기준의 조회 기간. 시작일과 종료일을 모두 포함한다."""

    start: date
    end: date


class InvalidPeriodError(ValueError):
    """조회 기간이 허용 범위를 벗어났다."""

    def __init__(self, reason: InvalidPeriodReason) -> None:
        super().__init__("허용하지 않은 조회 기간이다")
        self.reason = reason


def resolve_period(start: date | None, end: date | None, today: date) -> DateRange:
    """조회 기간을 검증한다. 둘 다 없으면 오늘을 포함한 최근 30일을 쓴다."""
    if start is None and end is None:
        return DateRange(
            start=today - timedelta(days=DEFAULT_PERIOD_DAYS - 1), end=today
        )
    if start is None or end is None:
        raise InvalidPeriodError(InvalidPeriodReason.INCOMPLETE)
    if start > end:
        raise InvalidPeriodError(InvalidPeriodReason.START_AFTER_END)
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise InvalidPeriodError(InvalidPeriodReason.TOO_LONG)
    return DateRange(start=start, end=end)

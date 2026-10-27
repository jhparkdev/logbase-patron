from datetime import date, timedelta

import pytest

from app.services.simulation_period import (
    DEFAULT_PERIOD_DAYS,
    MAX_PERIOD_DAYS,
    DateRange,
    InvalidPeriodError,
    InvalidPeriodReason,
    resolve_period,
)

TODAY = date(2026, 10, 27)


def _length(period: DateRange) -> int:
    return (period.end - period.start).days + 1


def _range_of(days: int) -> tuple[date, date]:
    return TODAY - timedelta(days=days - 1), TODAY


def test_limits_are_thirty_default_and_366_max() -> None:
    assert (DEFAULT_PERIOD_DAYS, MAX_PERIOD_DAYS) == (30, 366)


def test_no_period_means_last_30_days_including_today() -> None:
    period = resolve_period(None, None, TODAY)
    assert period == DateRange(date(2026, 9, 28), TODAY)
    assert _length(period) == 30


def test_default_period_crosses_month_boundary_correctly() -> None:
    # 2026년 2월은 28일까지다
    assert resolve_period(None, None, date(2026, 3, 1)).start == date(2026, 1, 31)


# 경계값은 바로 전, 정확히 그 값, 바로 후를 모두 검사한다
@pytest.mark.parametrize("days", [1, 30, 365, 366])
def test_period_up_to_366_days_is_accepted(days: int) -> None:
    start, end = _range_of(days)
    assert resolve_period(start, end, TODAY) == DateRange(start, end)


@pytest.mark.parametrize("days", [367, 368, 1000])
def test_period_longer_than_366_days_is_rejected(days: int) -> None:
    start, end = _range_of(days)
    with pytest.raises(InvalidPeriodError) as error:
        resolve_period(start, end, TODAY)
    assert error.value.reason == InvalidPeriodReason.TOO_LONG


def test_leap_year_full_year_is_exactly_366_days() -> None:
    assert resolve_period(date(2024, 1, 1), date(2024, 12, 31), TODAY)


def test_one_day_beyond_a_year_and_a_day_is_rejected() -> None:
    with pytest.raises(InvalidPeriodError):
        resolve_period(date(2025, 1, 1), date(2026, 1, 2), TODAY)


def test_single_day_period_is_accepted() -> None:
    assert resolve_period(TODAY, TODAY, TODAY) == DateRange(TODAY, TODAY)


def test_start_after_end_is_rejected() -> None:
    with pytest.raises(InvalidPeriodError) as error:
        resolve_period(TODAY, TODAY - timedelta(days=1), TODAY)
    assert error.value.reason == InvalidPeriodReason.START_AFTER_END


@pytest.mark.parametrize(
    ("start", "end"), [(TODAY, None), (None, TODAY)], ids=["start-only", "end-only"]
)
def test_only_one_of_start_and_end_is_rejected(
    start: date | None, end: date | None
) -> None:
    with pytest.raises(InvalidPeriodError) as error:
        resolve_period(start, end, TODAY)
    assert error.value.reason == InvalidPeriodReason.INCOMPLETE

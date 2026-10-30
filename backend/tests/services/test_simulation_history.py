from datetime import UTC, date, datetime

import pytest

from app.schemas.simulation_history import SimulationHistoryQuery
from app.services.simulation_history import resolve_history_period
from app.services.simulation_period import (
    DateRange,
    InvalidPeriodError,
    InvalidPeriodReason,
)

# KST 2026-10-28 09:00
NOW = datetime(2026, 10, 28, 0, tzinfo=UTC)
PAST_ID = "0192a3c4-0000-7000-8000-000000000001"


def test_without_conditions_the_last_30_kst_days_are_searched() -> None:
    period = resolve_history_period(SimulationHistoryQuery(), NOW)

    assert period == DateRange(date(2026, 9, 29), date(2026, 10, 28))


def test_dates_given_are_used_as_they_are() -> None:
    query = SimulationHistoryQuery(start_date="2026-01-01", end_date="2026-01-31")

    assert resolve_history_period(query, NOW) == DateRange(
        date(2026, 1, 1), date(2026, 1, 31)
    )


def test_searching_by_id_alone_is_not_limited_to_the_default_period() -> None:
    # ID 를 아는 실행은 30일보다 오래되었어도 찾을 수 있어야 한다
    query = SimulationHistoryQuery(simulation_id=PAST_ID)

    assert resolve_history_period(query, NOW) is None


def test_searching_by_id_with_dates_still_applies_the_dates() -> None:
    query = SimulationHistoryQuery(
        simulation_id=PAST_ID, start_date="2026-10-01", end_date="2026-10-02"
    )

    assert resolve_history_period(query, NOW) == DateRange(
        date(2026, 10, 1), date(2026, 10, 2)
    )


@pytest.mark.parametrize(
    ("start", "end", "reason"),
    [
        ("2026-10-01", None, InvalidPeriodReason.INCOMPLETE),
        ("2026-10-02", "2026-10-01", InvalidPeriodReason.START_AFTER_END),
        ("2025-01-01", "2026-01-02", InvalidPeriodReason.TOO_LONG),
    ],
)
def test_an_invalid_period_is_rejected_even_with_an_id(
    start: str, end: str | None, reason: InvalidPeriodReason
) -> None:
    query = SimulationHistoryQuery(
        simulation_id=PAST_ID, start_date=start, end_date=end
    )

    with pytest.raises(InvalidPeriodError) as error:
        resolve_history_period(query, NOW)
    assert error.value.reason == reason

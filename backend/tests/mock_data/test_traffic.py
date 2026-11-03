"""app/mock_data/traffic.py 테스트: 요일·공휴일·시간대에 따른 호출량."""

from datetime import date
from random import Random

from app.mock_data import traffic
from app.mock_data.period import KST, PERIOD_END

TUESDAY = date(2026, 10, 13)
SATURDAY = date(2026, 10, 17)
CHUSEOK = date(2026, 9, 25)


def test_weekends_and_holidays_are_quieter_than_weekdays() -> None:
    assert traffic.day_factor(SATURDAY) < traffic.day_factor(TUESDAY)
    assert traffic.day_factor(CHUSEOK) < traffic.day_factor(TUESDAY)


def test_sampled_time_stays_on_the_given_kst_day() -> None:
    rng = Random(3)

    for profile in traffic.HourProfile:
        for _ in range(200):
            at = traffic.sample_time(TUESDAY, profile, rng)
            assert at.astimezone(KST).date() == TUESDAY


def test_business_profile_is_busier_in_the_afternoon_than_at_dawn() -> None:
    rng = Random(3)
    hours = [
        traffic.sample_time(TUESDAY, traffic.HourProfile.BUSINESS, rng).hour
        for _ in range(2000)
    ]

    assert hours.count(15) > hours.count(4) * 3


def test_nightly_batch_profile_runs_mostly_before_dawn() -> None:
    rng = Random(3)
    hours = [
        traffic.sample_time(TUESDAY, traffic.HourProfile.NIGHTLY_BATCH, rng).hour
        for _ in range(500)
    ]

    assert sum(1 for h in hours if h < 6) > len(hours) / 2


def test_poisson_average_is_close_to_the_requested_mean() -> None:
    rng = Random(3)
    draws = [traffic.poisson(6.0, rng) for _ in range(3000)]

    assert 5.7 < sum(draws) / len(draws) < 6.3
    assert min(draws) >= 0


def test_days_cover_the_period_up_to_the_end_date() -> None:
    days = traffic.period_days()

    assert days[0] == date(2026, 8, 1)
    assert days[-1] == PERIOD_END.astimezone(KST).date()

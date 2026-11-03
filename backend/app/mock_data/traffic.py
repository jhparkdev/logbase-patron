"""호출량의 시간 패턴: 요일·공휴일 배율, 시간대 분포, 하루 건수 추첨."""

import math
from datetime import date, datetime, timedelta
from enum import StrEnum
from random import Random

from app.mock_data.period import KST, PERIOD_END, PERIOD_START

# 월요일=0. 주말은 쇼핑몰 운영자가 상품을 덜 등록한다.
WEEKDAY_FACTORS = (1.05, 1.0, 1.0, 1.0, 0.95, 0.45, 0.35)
HOLIDAY_FACTOR = 0.4
# 2026년 기간 안의 공휴일: 광복절 대체공휴일, 추석 연휴, 개천절 대체공휴일, 한글날
HOLIDAYS = frozenset(
    {
        date(2026, 8, 17),
        date(2026, 9, 24),
        date(2026, 9, 25),
        date(2026, 9, 26),
        date(2026, 10, 5),
        date(2026, 10, 9),
    }
)
HOURS_PER_DAY = 24
SECONDS_PER_HOUR = 3600


class HourProfile(StrEnum):
    BUSINESS = "BUSINESS"  # 사람이 화면에서 요청하는 서비스
    NIGHTLY_BATCH = "NIGHTLY_BATCH"  # 새벽에 카탈로그를 한꺼번에 처리하는 서비스


# 시간대(0~23시, KST)별 상대 비중
# fmt: off
HOUR_WEIGHTS = {
    HourProfile.BUSINESS: (
        0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 1.6, 1.6,
        0.9, 1.3, 1.5, 1.6, 1.5, 1.3, 1.0, 0.7, 0.6, 0.5, 0.4, 0.3,
    ),
    HourProfile.NIGHTLY_BATCH: (
        0.3, 1.0, 3.0, 3.0, 2.0, 0.5, 0.2, 0.2, 0.3, 0.4, 0.5, 0.5,
        0.3, 0.4, 0.5, 0.5, 0.4, 0.3, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2,
    ),
}
# fmt: on


def day_factor(day: date) -> float:
    if day in HOLIDAYS:
        return HOLIDAY_FACTOR
    return WEEKDAY_FACTORS[day.weekday()]


def period_days() -> list[date]:
    first = PERIOD_START.astimezone(KST).date()
    last = PERIOD_END.astimezone(KST).date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def sample_time(day: date, profile: HourProfile, rng: Random) -> datetime:
    hour = rng.choices(range(HOURS_PER_DAY), weights=HOUR_WEIGHTS[profile])[0]
    second = rng.randrange(SECONDS_PER_HOUR)
    start = datetime(day.year, day.month, day.day, hour, tzinfo=KST)
    return start + timedelta(seconds=second)


def poisson(mean: float, rng: Random) -> int:
    """하루 건수 추첨(Knuth 방식). 생성기의 평균은 수십 이하라 충분히 빠르다."""
    limit, count, product = math.exp(-mean), 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count

"""고객·서비스별 작업 수요. 호출량 규모(전체 약 5천 건)는 이 표의 숫자로 맞춘다.

하루 평균 작업 수 = 평일 기준 작업 수 × 월 성장률^(경과 일수/30) × 요일·공휴일 배율 × 행사 배율
"""

from dataclasses import dataclass
from datetime import date

from app.mock_data import routes
from app.mock_data.organizations import AI_PDP, FLIPPAGE
from app.mock_data.routes import Route

DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Demand:
    customer_id: int
    service_code: str
    tasks_per_weekday: float  # 사용을 시작한 달의 평일 하루 작업 수
    monthly_growth: float
    writer: Route  # AI PDP는 문구 작성, FlipPage는 카탈로그 요약 경로
    rewriter: Route | None = None  # 평가에서 떨어진 문구를 다시 쓰는 경로
    spikes: tuple[tuple[date, float], ...] = ()  # 기획전 등 행사일 배율


DEMANDS = (
    Demand(
        1, AI_PDP, 9.0, 1.12, routes.PDP_WRITER, routes.PDP_PREMIUM_REWRITER,
        ((date(2026, 10, 22), 2.2), (date(2026, 10, 23), 1.8)),  # F/W 시즌 기획전
    ),
    Demand(1, FLIPPAGE, 3.0, 1.08, routes.CATALOG_SUMMARIZER),
    Demand(
        2, AI_PDP, 6.0, 1.05, routes.PDP_WRITER_BUDGET, routes.PDP_WRITER_BUDGET,
        tuple((date(2026, 9, day), 1.6) for day in range(14, 19)),  # 추석 선물 기획전
    ),
    Demand(
        3, AI_PDP, 3.0, 1.6, routes.PDP_WRITER_BEAUTY, routes.PDP_WRITER_BEAUTY,
        tuple((date(2026, 11, day), 1.8) for day in range(3, 6)),  # 연말 행사 상품 등록
    ),
    Demand(4, FLIPPAGE, 4.0, 1.03, routes.CATALOG_SUMMARIZER_LIGHT),
    Demand(5, AI_PDP, 2.0, 1.3, routes.PDP_WRITER_LIVING, routes.PDP_WRITER_LIVING),
    Demand(6, AI_PDP, 5.0, 0.9, routes.PDP_WRITER, routes.PDP_WRITER),
)  # fmt: skip


def spike_factor(demand: Demand, day: date) -> float:
    return next(
        (factor for spike_day, factor in demand.spikes if spike_day == day), 1.0
    )

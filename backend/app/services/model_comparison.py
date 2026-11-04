"""새 모델과 기본 모델의 비교 판단(P-03). 값만 받아 계산한다."""

from dataclasses import dataclass
from decimal import Decimal

from app.services.provider_ranking import Workload, expected_cost

IMPROVEMENT_THRESHOLD_PCT = Decimal(5)
PERCENT = Decimal(100)


@dataclass(frozen=True)
class CallMetrics:
    cost_usd: Decimal | None
    latency_ms: int | None


@dataclass(frozen=True)
class Prices:
    input: Decimal | None
    output: Decimal | None


@dataclass(frozen=True)
class Comparison:
    cost_change_pct: Decimal | None
    latency_change_pct: Decimal | None
    cheaper: bool | None
    faster: bool | None

    @property
    def worth_checking(self) -> bool | None:
        if self.cheaper is True or self.faster is True:
            return True
        if self.cheaper is None and self.faster is None:
            return None
        return False


def change_pct(base: Decimal | None, new: Decimal | None) -> Decimal | None:
    """기본 값 대비 증감률(%). 모르는 값이 있거나 기본 값이 0이면 None."""
    if base is None or new is None or base == 0:
        return None
    return (new - base) / base * PERCENT


def _improved(pct: Decimal | None) -> bool | None:
    if pct is None:
        return None
    return pct <= -IMPROVEMENT_THRESHOLD_PCT


def compare(base: CallMetrics, new: CallMetrics) -> Comparison:
    cost_pct = change_pct(base.cost_usd, new.cost_usd)
    latency_pct = change_pct(
        None if base.latency_ms is None else Decimal(base.latency_ms),
        None if new.latency_ms is None else Decimal(new.latency_ms),
    )
    return Comparison(
        cost_change_pct=cost_pct,
        latency_change_pct=latency_pct,
        cheaper=_improved(cost_pct),
        faster=_improved(latency_pct),
    )


def is_too_expensive(
    base: Prices, new: Prices, workload: Workload, *, max_ratio: Decimal
) -> bool:
    """같은 작업량의 예상 비용이 기본 모델의 max_ratio배를 넘거나 단가를 모르면 True."""
    if None in (base.input, base.output, new.input, new.output):
        return True
    base_cost = expected_cost(workload, base.input, base.output, None)  # type: ignore[arg-type]
    new_cost = expected_cost(workload, new.input, new.output, None)  # type: ignore[arg-type]
    return new_cost > base_cost * max_ratio


def estimate_max_cost(
    *, prompt_chars: int, max_tokens: int, prices: Prices
) -> Decimal | None:
    """호출 한 번의 최대 비용. 입력은 글자당 토큰 1개, 출력은 상한까지로 잡는다."""
    if prices.input is None or prices.output is None:
        return None
    return Decimal(prompt_chars) * prices.input + Decimal(max_tokens) * prices.output


def fits_budget(*, spent_today: Decimal, estimate: Decimal, daily_cap: Decimal) -> bool:
    return spent_today + estimate <= daily_cap

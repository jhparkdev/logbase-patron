"""월 예산 사용률과 상태 판단. DB 없이 호출하는 순수 함수다."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

# 경고·초과 기준은 고정이다(P-01·P-02 결정). budgets.warning_threshold_pct 는 화면에서 입력받지 않아 쓰지 않는다
WARNING_PCT = Decimal(80)
OVER_PCT = Decimal(100)
HUNDRED = Decimal(100)
PCT_PRECISION = Decimal("0.01")


class BudgetStatus(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    OVER = "OVER"
    UNSET = "UNSET"  # 예산 없음. 사용률 0%와 다르다


@dataclass(frozen=True)
class BudgetEvaluation:
    used_usd: Decimal  # 확정 + 추정. 미확인은 금액을 모르므로 포함하지 않는다
    usage_pct: Decimal | None
    confirmed_usage_pct: Decimal | None
    remaining_usd: Decimal | None
    status: BudgetStatus


def evaluate_budget(
    monthly_amount: Decimal | None, confirmed: Decimal, estimated: Decimal
) -> BudgetEvaluation:
    used = confirmed + estimated
    if monthly_amount is None:
        return BudgetEvaluation(used, None, None, None, BudgetStatus.UNSET)
    return BudgetEvaluation(
        used_usd=used,
        usage_pct=_rounded_pct(used, monthly_amount),
        confirmed_usage_pct=_rounded_pct(confirmed, monthly_amount),
        remaining_usd=monthly_amount - used,
        # 반올림 전 값으로 판단한다. 79.999%가 80%로 올라가 주의가 되면 안 된다
        status=_status(used * HUNDRED / monthly_amount),
    )


def share_of_budget(used: Decimal, monthly_amount: Decimal | None) -> Decimal | None:
    """사용액이 월 예산의 몇 %인지. 예산이 없으면 None."""
    return None if monthly_amount is None else _rounded_pct(used, monthly_amount)


def _status(pct: Decimal) -> BudgetStatus:
    if pct >= OVER_PCT:
        return BudgetStatus.OVER
    if pct >= WARNING_PCT:
        return BudgetStatus.WARNING
    return BudgetStatus.NORMAL


def _rounded_pct(value: Decimal, base: Decimal) -> Decimal:
    return (value * HUNDRED / base).quantize(PCT_PRECISION, ROUND_HALF_UP)

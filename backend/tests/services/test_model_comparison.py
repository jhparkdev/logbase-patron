"""services/model_comparison.py 테스트. 새 모델과 기본 모델의 비교 판단·사전 거름·비용 상한을 DB 없이 본다."""

from decimal import Decimal

import pytest

from app.services.model_comparison import (
    CallMetrics,
    Prices,
    change_pct,
    compare,
    estimate_max_cost,
    fits_budget,
    is_too_expensive,
)
from app.services.provider_ranking import Workload

WORKLOAD = Workload(input_tokens=1000, output_tokens=500)


@pytest.mark.parametrize(
    ("base", "new", "expected"),
    [
        ("100", "90", "-10"),
        ("100", "100", "0"),
        ("0.002", "0.003", "50"),
        ("200", "100", "-50"),
    ],
)
def test_증감률은_새_값이_기본_값보다_얼마나_바뀌었는지_퍼센트로_구한다(
    base: str, new: str, expected: str
) -> None:
    assert change_pct(Decimal(base), Decimal(new)) == Decimal(expected)


@pytest.mark.parametrize(
    ("base", "new"),
    [(None, Decimal(1)), (Decimal(1), None), (None, None), (Decimal(0), Decimal(1))],
)
def test_값을_모르거나_기본_값이_0이면_증감률을_구하지_않는다(
    base: Decimal | None, new: Decimal | None
) -> None:
    # 모르는 값을 0으로 보고 싸다고 판단하지 않는다
    assert change_pct(base, new) is None


def test_비용이_5퍼센트_이상_싸면_저렴하다고_본다() -> None:
    result = compare(
        CallMetrics(cost_usd=Decimal("0.0100"), latency_ms=1000),
        CallMetrics(cost_usd=Decimal("0.0095"), latency_ms=1000),
    )

    assert result.cost_change_pct == Decimal(-5)
    assert result.cheaper is True


def test_비용이_5퍼센트_미만으로만_싸면_저렴하다고_보지_않는다() -> None:
    result = compare(
        CallMetrics(cost_usd=Decimal("0.0100"), latency_ms=1000),
        CallMetrics(cost_usd=Decimal("0.0096"), latency_ms=1000),
    )

    assert result.cheaper is False


def test_시간이_5퍼센트_이상_짧으면_빠르다고_본다() -> None:
    result = compare(
        CallMetrics(cost_usd=Decimal(1), latency_ms=2000),
        CallMetrics(cost_usd=Decimal(1), latency_ms=1900),
    )

    assert result.latency_change_pct == Decimal(-5)
    assert result.faster is True


def test_더_비싸고_느리면_둘_다_아니다() -> None:
    result = compare(
        CallMetrics(cost_usd=Decimal(1), latency_ms=1000),
        CallMetrics(cost_usd=Decimal(2), latency_ms=3000),
    )

    assert result.cheaper is False
    assert result.faster is False
    assert result.worth_checking is False


@pytest.mark.parametrize(
    ("cheaper_cost", "faster_latency"),
    [(Decimal("0.5"), 1000), (Decimal(1), 500)],
)
def test_저렴하거나_빠르면_확인해_볼_만하다고_알린다(
    cheaper_cost: Decimal, faster_latency: int
) -> None:
    result = compare(
        CallMetrics(cost_usd=Decimal(1), latency_ms=1000),
        CallMetrics(cost_usd=cheaper_cost, latency_ms=faster_latency),
    )

    assert result.worth_checking is True


def test_비용을_모르면_저렴한지_판단하지_않고_시간만_판단한다() -> None:
    result = compare(
        CallMetrics(cost_usd=Decimal(1), latency_ms=1000),
        CallMetrics(cost_usd=None, latency_ms=500),
    )

    assert result.cost_change_pct is None
    assert result.cheaper is None
    assert result.faster is True
    assert result.worth_checking is True


def test_둘_다_모르면_확인해_볼_만한지도_모른다() -> None:
    result = compare(
        CallMetrics(cost_usd=None, latency_ms=None),
        CallMetrics(cost_usd=None, latency_ms=None),
    )

    assert result.cheaper is None
    assert result.faster is None
    assert result.worth_checking is None


def test_단가가_기본_모델의_몇_배를_넘으면_호출하지_않는다() -> None:
    base = Prices(input=Decimal("0.000001"), output=Decimal("0.000002"))
    pricey = Prices(input=Decimal("0.00001"), output=Decimal("0.00002"))

    assert is_too_expensive(base, pricey, WORKLOAD, max_ratio=Decimal(5)) is True


def test_단가가_배수_안이면_호출한다() -> None:
    base = Prices(input=Decimal("0.000001"), output=Decimal("0.000002"))
    near = Prices(input=Decimal("0.000004"), output=Decimal("0.000008"))

    assert is_too_expensive(base, near, WORKLOAD, max_ratio=Decimal(5)) is False


def test_더_싼_모델은_거르지_않는다() -> None:
    base = Prices(input=Decimal("0.00001"), output=Decimal("0.00002"))
    cheap = Prices(input=Decimal("0.000001"), output=Decimal("0.000002"))

    assert is_too_expensive(base, cheap, WORKLOAD, max_ratio=Decimal(5)) is False


def test_새_모델_단가를_모르면_호출하지_않는다() -> None:
    base = Prices(input=Decimal("0.000001"), output=Decimal("0.000002"))
    unknown = Prices(input=None, output=Decimal("0.000002"))

    assert is_too_expensive(base, unknown, WORKLOAD, max_ratio=Decimal(5)) is True


def test_호출_한_번의_최대_비용은_입력을_글자_수만큼_출력을_상한까지_쓴_값이다() -> (
    None
):
    cost = estimate_max_cost(
        prompt_chars=300,
        max_tokens=1000,
        prices=Prices(input=Decimal("0.000001"), output=Decimal("0.000002")),
    )

    # 300 * 0.000001 + 1000 * 0.000002
    assert cost == Decimal("0.0023")


def test_단가를_모르면_최대_비용도_모른다() -> None:
    assert (
        estimate_max_cost(
            prompt_chars=300,
            max_tokens=1000,
            prices=Prices(input=None, output=Decimal("0.000002")),
        )
        is None
    )


@pytest.mark.parametrize(
    ("spent", "estimate", "cap", "expected"),
    [
        ("0.5", "0.4", "1", True),
        ("0.5", "0.5", "1", True),
        ("0.5", "0.51", "1", False),
        ("1", "0", "1", True),
    ],
)
def test_오늘_쓴_돈과_이번_호출의_최대_비용을_더해_상한을_넘으면_호출하지_않는다(
    spent: str, estimate: str, cap: str, expected: bool
) -> None:
    assert (
        fits_budget(
            spent_today=Decimal(spent),
            estimate=Decimal(estimate),
            daily_cap=Decimal(cap),
        )
        is expected
    )

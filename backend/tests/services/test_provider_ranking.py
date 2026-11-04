"""services/provider_ranking.py 테스트. 업체별 예상 총비용 계산과 순위, 제외 규칙을 DB 없이 본다."""

from decimal import Decimal

import pytest

from app.openrouter.lookup_result import EndpointInfo
from app.schemas.provider_ranking import ExcludedReason
from app.services.provider_ranking import (
    Ranking,
    Workload,
    expected_cost,
    provider_order,
    rank_providers,
)

MIN_UPTIME = Decimal(90)


def endpoint(
    name: str,
    *,
    prompt: str | None = "0.000002",
    completion: str | None = "0.00001",
    cache_read: str | None = None,
    cache_write: str | None = None,
    status: int | None = 0,
    uptime: str | None = "99.5",
    uptime_30m: str | None = None,
) -> EndpointInfo:
    pricing = {
        key: Decimal(value)
        for key, value in {
            "prompt": prompt,
            "completion": completion,
            "input_cache_read": cache_read,
            "input_cache_write": cache_write,
        }.items()
        if value is not None
    }
    return EndpointInfo(
        provider_name=name,
        status=status,
        uptime_last_1d=None if uptime is None else Decimal(uptime),
        uptime_last_30m=None if uptime_30m is None else Decimal(uptime_30m),
        pricing=pricing,
    )


WORKLOAD = Workload(input_tokens=1000, output_tokens=500)


def names(result: Ranking) -> list[str]:
    return [item.name for item in result.ranked]


# ---------------------------------------------------------------
# 예상 비용 계산
# ---------------------------------------------------------------
def test_캐시가_없으면_입력과_출력_단가로만_계산한다() -> None:
    cost = expected_cost(
        WORKLOAD,
        input_price=Decimal("0.000002"),
        output_price=Decimal("0.00001"),
        cache_read_price=None,
    )

    assert cost == Decimal("0.007")  # 1000×0.000002 + 500×0.00001


def test_캐시_적중분은_캐시_읽기_단가로_계산한다() -> None:
    workload = Workload(1000, 500, cache_hit_ratio=Decimal("0.5"))

    cost = expected_cost(
        workload,
        input_price=Decimal("0.000002"),
        output_price=Decimal("0.00001"),
        cache_read_price=Decimal("0.0000002"),
    )

    # 500×0.000002 + 500×0.0000002 + 500×0.00001
    assert cost == Decimal("0.006100")


def test_캐시_단가가_없는_업체는_적중_비율이_있어도_할인하지_않는다() -> None:
    workload = Workload(1000, 500, cache_hit_ratio=Decimal("0.9"))

    with_ratio = expected_cost(workload, Decimal("0.000002"), Decimal("0.00001"), None)
    without = expected_cost(WORKLOAD, Decimal("0.000002"), Decimal("0.00001"), None)

    assert with_ratio == without


def test_캐시_읽기_단가가_0이어도_계산한다() -> None:
    workload = Workload(1000, 0, cache_hit_ratio=Decimal(1))

    cost = expected_cost(workload, Decimal("0.000002"), Decimal("0.00001"), Decimal(0))

    assert cost == Decimal(0)


def test_금액은_float_오차_없이_정확하게_계산한다() -> None:
    cost = expected_cost(
        Workload(3, 0),
        input_price=Decimal("0.0000000042"),
        output_price=Decimal(0),
        cache_read_price=None,
    )

    assert cost == Decimal("0.0000000126")


# ---------------------------------------------------------------
# 순위
# ---------------------------------------------------------------
def test_예상_총비용이_싼_순서로_정렬한다() -> None:
    result = rank_providers(
        [
            endpoint("Pricey", prompt="0.000005"),
            endpoint("Cheap", prompt="0.000001"),
            endpoint("Mid", prompt="0.000003"),
        ],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert names(result) == ["Cheap", "Mid", "Pricey"]
    assert result.ranked[0].expected_cost_usd < result.ranked[1].expected_cost_usd


def test_비용이_같으면_이름순이다() -> None:
    result = rank_providers(
        [endpoint("B"), endpoint("A")], WORKLOAD, min_uptime=MIN_UPTIME
    )

    assert names(result) == ["A", "B"]


def test_입력_단가가_더_싸도_캐시를_쓰면_뒤집힐_수_있다() -> None:
    cheap_input = endpoint("NoCache", prompt="0.000001")
    cache_friendly = endpoint("Cache", prompt="0.0000015", cache_read="0.00000005")
    heavy_cache = Workload(10000, 100, cache_hit_ratio=Decimal("0.9"))

    no_cache_load = rank_providers(
        [cheap_input, cache_friendly], Workload(10000, 100), min_uptime=MIN_UPTIME
    )
    cache_load = rank_providers(
        [cheap_input, cache_friendly], heavy_cache, min_uptime=MIN_UPTIME
    )

    assert names(no_cache_load) == ["NoCache", "Cache"]
    assert names(cache_load) == ["Cache", "NoCache"]


def test_순위에_단가와_캐시_지원_여부를_담는다() -> None:
    result = rank_providers(
        [endpoint("A", cache_read="0.0000002", cache_write="0.0000025"), endpoint("B")],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    a, b = result.ranked
    assert a.supports_caching is True
    assert a.cache_read_price == Decimal("0.0000002")
    assert a.cache_write_price == Decimal("0.0000025")
    assert (b.supports_caching, b.cache_read_price) == (False, None)
    assert a.input_price == Decimal("0.000002")
    assert a.output_price == Decimal("0.00001")


# ---------------------------------------------------------------
# 제외 규칙
# ---------------------------------------------------------------
def test_상태가_정상이_아닌_업체는_뺀다() -> None:
    result = rank_providers(
        [endpoint("Bad", status=-1), endpoint("Good")], WORKLOAD, min_uptime=MIN_UPTIME
    )

    assert names(result) == ["Good"]
    assert [(item.name, item.reason) for item in result.excluded] == [
        ("Bad", ExcludedReason.STATUS_NOT_OK)
    ]


def test_가동률이_기준_미만인_업체는_빼고_기준과_같으면_남긴다() -> None:
    result = rank_providers(
        [
            endpoint("Low", uptime="89.99"),
            endpoint("Exact", uptime="90"),
            endpoint("High", uptime="99"),
        ],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert sorted(names(result)) == ["Exact", "High"]
    assert [(item.name, item.reason) for item in result.excluded] == [
        ("Low", ExcludedReason.LOW_UPTIME)
    ]


def test_최근_30분_가동률이_있으면_그것으로_판단한다() -> None:
    result = rank_providers(
        [
            # 하루 가동률은 좋지만 지금은 나쁨
            endpoint("DownNow", uptime="99.9", uptime_30m="40"),
            # 하루 가동률은 나쁘지만 지금은 회복
            endpoint("Recovered", uptime="50", uptime_30m="99"),
        ],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert names(result) == ["Recovered"]
    assert [(item.name, item.reason) for item in result.excluded] == [
        ("DownNow", ExcludedReason.LOW_UPTIME)
    ]


def test_최근_30분_가동률이_없으면_하루_가동률로_판단한다() -> None:
    result = rank_providers(
        [endpoint("Low", uptime="50"), endpoint("High", uptime="99")],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert names(result) == ["High"]


@pytest.mark.parametrize(
    "missing", [{"prompt": None}, {"completion": None}], ids=["입력 단가", "출력 단가"]
)
def test_입력이나_출력_단가를_모르면_0으로_계산하지_않고_뺀다(
    missing: dict[str, None],
) -> None:
    result = rank_providers(
        [endpoint("Unknown", **missing), endpoint("Known")],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert names(result) == ["Known"]
    assert [(item.name, item.reason) for item in result.excluded] == [
        ("Unknown", ExcludedReason.PRICE_UNKNOWN)
    ]


def test_상태와_가동률을_모르면_그것만으로는_빼지_않는다() -> None:
    result = rank_providers(
        [endpoint("Unsure", status=None, uptime=None)], WORKLOAD, min_uptime=MIN_UPTIME
    )

    assert names(result) == ["Unsure"]
    assert result.excluded == []


def test_여러_이유가_겹치면_상태_가동률_단가_순으로_하나만_알린다() -> None:
    result = rank_providers(
        [
            endpoint("All", status=1, uptime="10", prompt=None),
            endpoint("UptimeAndPrice", uptime="10", prompt=None),
        ],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert {item.name: item.reason for item in result.excluded} == {
        "All": ExcludedReason.STATUS_NOT_OK,
        "UptimeAndPrice": ExcludedReason.LOW_UPTIME,
    }


def test_모두_빠지면_순위가_비고_빠진_이유는_남는다() -> None:
    result = rank_providers([endpoint("A", status=2)], WORKLOAD, min_uptime=MIN_UPTIME)

    assert result.ranked == []
    assert len(result.excluded) == 1


def test_업체가_없으면_빈_결과이다() -> None:
    result = rank_providers([], WORKLOAD, min_uptime=MIN_UPTIME)

    assert (result.ranked, result.excluded) == ([], [])


# ---------------------------------------------------------------
# 호출 요청에 넣을 업체 순서
# ---------------------------------------------------------------
def test_업체_순서는_싼_순서의_이름_목록이고_제외된_업체는_넣지_않는다() -> None:
    result = rank_providers(
        [
            endpoint("Pricey", prompt="0.000005"),
            endpoint("Down", status=-1),
            endpoint("Cheap", prompt="0.000001"),
        ],
        WORKLOAD,
        min_uptime=MIN_UPTIME,
    )

    assert provider_order(result) == ["Cheap", "Pricey"]


def test_순위가_비면_업체_순서도_비어_있다() -> None:
    result = rank_providers([endpoint("A", status=2)], WORKLOAD, min_uptime=MIN_UPTIME)

    assert provider_order(result) == []

"""서버 업체 예상 총비용 순위(P-03). 단가와 가정(토큰 수, 캐시 적중 비율)으로 DB 없이 계산한다.

예상 총비용 = (캐시가 아닌 입력 × 입력 단가) + (캐시 입력 × 캐시 읽기 단가) + (출력 × 출력 단가).
실제 호출 한 건(Novita)의 청구액과 이 식이 정확히 맞는 것을 2차 실험에서 확인했다.
캐시 쓰기 비용은 넣지 않는다(처음 한 번만 드는 비용이라 반복 호출의 비교 기준으로 쓰지 않음).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.openrouter.lookup_result import EndpointInfo
from app.schemas.provider_ranking import ExcludedReason

# OpenRouter가 준 업체 상태에서 정상으로 확인한 값. 다른 값의 뜻은 확인하지 못했다
HEALTHY_STATUS = 0
PROMPT = "prompt"
COMPLETION = "completion"
CACHE_READ = "input_cache_read"
CACHE_WRITE = "input_cache_write"


@dataclass(frozen=True)
class Workload:
    """작업 한 번에 대한 가정."""

    input_tokens: int
    output_tokens: int
    # 입력 중 캐시에서 읽는 비율(0~1)
    cache_hit_ratio: Decimal = Decimal(0)


@dataclass(frozen=True)
class RankedProvider:
    name: str
    expected_cost_usd: Decimal
    input_price: Decimal
    output_price: Decimal
    cache_read_price: Decimal | None
    cache_write_price: Decimal | None

    @property
    def supports_caching(self) -> bool:
        return self.cache_read_price is not None


@dataclass(frozen=True)
class ExcludedProvider:
    name: str
    reason: ExcludedReason


@dataclass(frozen=True)
class Ranking:
    ranked: list[RankedProvider]
    excluded: list[ExcludedProvider]


def expected_cost(
    workload: Workload,
    input_price: Decimal,
    output_price: Decimal,
    cache_read_price: Decimal | None,
) -> Decimal:
    """작업 한 번의 예상 총비용. 캐시 읽기 단가가 없는 업체는 적중 비율이 있어도 할인하지 않는다."""
    input_tokens = Decimal(workload.input_tokens)
    cached = (
        input_tokens * workload.cache_hit_ratio if cache_read_price is not None else 0
    )
    fresh = input_tokens - cached
    cost = fresh * input_price + Decimal(workload.output_tokens) * output_price
    if cache_read_price is not None:
        cost += cached * cache_read_price
    # 곱셈이 남기는 끝자리 0(0.0060000)을 없애 같은 값은 같은 글자로 보이게 한다
    return cost.normalize()


def provider_order(ranking: Ranking) -> list[str]:
    """호출 요청의 provider.order에 넣을 업체 이름. 예상 총비용이 싼 순서이고 제외된 업체는 넣지 않는다."""
    return [item.name for item in ranking.ranked]


def _excluded_reason(
    endpoint: EndpointInfo, min_uptime: Decimal
) -> ExcludedReason | None:
    # 상태나 가동률을 모르는 것만으로는 빼지 않는다(알려진 나쁜 값만 거른다)
    if endpoint.status is not None and endpoint.status != HEALTHY_STATUS:
        return ExcludedReason.STATUS_NOT_OK
    # 지금 상태를 가장 잘 보여 주는 최근 30분 값을 먼저 쓰고, 없으면 하루 값을 쓴다
    uptime = (
        endpoint.uptime_last_30m
        if endpoint.uptime_last_30m is not None
        else endpoint.uptime_last_1d
    )
    if uptime is not None and uptime < min_uptime:
        return ExcludedReason.LOW_UPTIME
    if PROMPT not in endpoint.pricing or COMPLETION not in endpoint.pricing:
        return ExcludedReason.PRICE_UNKNOWN
    return None


def rank_providers(
    endpoints: Sequence[EndpointInfo], workload: Workload, *, min_uptime: Decimal
) -> Ranking:
    """업체를 예상 총비용이 싼 순서로 정렬한다(같으면 이름순). 거른 업체는 이유와 함께 따로 돌려준다."""
    ranked: list[RankedProvider] = []
    excluded: list[ExcludedProvider] = []
    for endpoint in endpoints:
        reason = _excluded_reason(endpoint, min_uptime)
        if reason is not None:
            excluded.append(ExcludedProvider(endpoint.provider_name, reason))
            continue
        pricing = endpoint.pricing
        ranked.append(
            RankedProvider(
                name=endpoint.provider_name,
                expected_cost_usd=expected_cost(
                    workload,
                    pricing[PROMPT],
                    pricing[COMPLETION],
                    pricing.get(CACHE_READ),
                ),
                input_price=pricing[PROMPT],
                output_price=pricing[COMPLETION],
                cache_read_price=pricing.get(CACHE_READ),
                cache_write_price=pricing.get(CACHE_WRITE),
            )
        )
    ranked.sort(key=lambda item: (item.expected_cost_usd, item.name))
    return Ranking(ranked=ranked, excluded=excluded)

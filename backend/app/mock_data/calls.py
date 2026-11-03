"""호출 1건(ai_requests 행)을 만든다: Token 수, 지연 시간, 결과, 비용.

비용은 OpenRouter가 응답에 주는 usage.cost를 흉내 내어 Token 수와 실제 단가로 계산한다.
비용이 정해지는 경로(응답, 나중 대조, 가격 추정)는 cost_fields가 현재 시각을 인자로 받아 판단한다.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from random import Random

from pydantic import JsonValue

from app.mock_data.costs import CostPath, cost_fields, sample_cost_path
from app.mock_data.ids import generation_id, sha256_hex, uuid7_at
from app.mock_data.model_book import ModelBook, ModelEntry
from app.mock_data.outcomes import Outcome
from app.mock_data.rows import Row
from app.models import CallPurpose, DataSource, RequestStatus, UsageOrigin

COST_QUANTUM = Decimal(1).scaleb(-12)
MS_PER_SECOND = 1000
LATENCY_SPREAD = (0.85, 1.25)  # 같은 모델·같은 길이라도 호출마다 달라지는 폭
CACHE_HIT_SHARE = 0.6  # 캐시 단가가 있는 모델에서 시스템 Prompt가 캐시에 맞는 비율
CACHED_FRACTION = (0.3, 0.7)
REASONING_SPREAD = (0.6, 1.4)
FINISH_STOP = "stop"


class Shape(StrEnum):
    """호출 종류별 Token 규모."""

    DESCRIPTION = "DESCRIPTION"
    EVALUATION = "EVALUATION"
    IMAGE_ANALYSIS = "IMAGE_ANALYSIS"
    CATALOG_SUMMARY = "CATALOG_SUMMARY"
    EXPERIMENT = "EXPERIMENT"
    CONNECTION_TEST = "CONNECTION_TEST"


# (입력 Token 범위, 출력 Token 범위)
TOKEN_RANGES = {
    Shape.DESCRIPTION: ((1800, 4200), (450, 1200)),
    Shape.EVALUATION: ((1500, 3200), (80, 260)),
    Shape.IMAGE_ANALYSIS: ((1100, 2600), (150, 420)),
    Shape.CATALOG_SUMMARY: ((3000, 9000), (280, 700)),
    Shape.EXPERIMENT: ((800, 6000), (100, 1500)),
    Shape.CONNECTION_TEST: ((14, 18), (1, 3)),
}
EXECUTION_CONFIGS: dict[Shape, dict[str, JsonValue]] = {
    Shape.DESCRIPTION: {"temperature": 0.7, "max_tokens": 2048},
    Shape.EVALUATION: {"temperature": 0, "max_tokens": 512},
    Shape.IMAGE_ANALYSIS: {"temperature": 0.2, "max_tokens": 1024},
    Shape.CATALOG_SUMMARY: {"temperature": 0.3, "max_tokens": 1024},
    Shape.EXPERIMENT: {"temperature": 0.7, "max_tokens": 4096},
    Shape.CONNECTION_TEST: {"temperature": 0, "max_tokens": 64},
}


@dataclass(frozen=True)
class CallSpec:
    usage_origin: UsageOrigin
    key_id: int
    service_id: int
    model_id: int
    shape: Shape
    call_purpose: CallPurpose
    customer_id: int | None = None
    project_id: int | None = None
    executed_by: int | None = None
    task_id: uuid.UUID | None = None
    simulation_id: uuid.UUID | None = None
    attempt_no: int = 1
    parent_request_id: uuid.UUID | None = None
    routing_policy: dict[str, JsonValue] = field(default_factory=dict)
    input_reference: str | None = None
    # 실행 Provider를 고정한 호출(시뮬레이션)은 요청한 Provider가 그대로 실제 Provider가 된다
    requested_provider: str | None = None
    execution_config: dict[str, JsonValue] | None = None  # None이면 호출 종류의 기본값
    # (입력 Token, 보이는 출력 Token). 원문이 있는 호출은 글 길이에서 계산해 넘긴다
    tokens: tuple[int, int] | None = None
    input_hash: str | None = (
        None  # None이면 호출마다 다른 값. 시뮬레이션은 실행의 입력 해시
    )


def call_cost(
    entry: ModelEntry, input_tokens: int, output_tokens: int, cached: int
) -> Decimal:
    cache_price = (
        entry.cache_read_price
        if entry.cache_read_price is not None
        else entry.input_price
    )
    cost = (
        (input_tokens - cached) * entry.input_price
        + cached * cache_price
        + output_tokens * entry.output_price
    )
    return cost.quantize(COST_QUANTUM)


@dataclass(frozen=True)
class _Usage:
    input_tokens: int
    output_tokens: int
    cached: int
    reasoning: int
    latency_ms: int


def _sample_usage(entry: ModelEntry, spec: CallSpec, rng: Random) -> _Usage:
    if spec.tokens is not None:
        input_tokens, visible_tokens = spec.tokens
    else:
        (in_low, in_high), (out_low, out_high) = TOKEN_RANGES[spec.shape]
        input_tokens = rng.randint(in_low, in_high)
        visible_tokens = rng.randint(out_low, out_high)
    cached = 0
    if entry.cache_read_price is not None and rng.random() < CACHE_HIT_SHARE:
        cached = int(input_tokens * rng.uniform(*CACHED_FRACTION))
    profile = entry.profile
    # 추론 Token은 보이는 답 위에 더해지고, 출력 Token에 포함되어 청구된다
    reasoning = int(
        visible_tokens * profile.reasoning_share * rng.uniform(*REASONING_SPREAD)
    )
    output_tokens = visible_tokens + reasoning
    generating_ms = output_tokens / profile.tokens_per_second * MS_PER_SECOND
    latency = int(
        (profile.first_token_ms + generating_ms) * rng.uniform(*LATENCY_SPREAD)
    )
    return _Usage(input_tokens, output_tokens, cached, reasoning, latency)


def build_call(
    spec: CallSpec,
    requested_at: datetime,
    outcome: Outcome,
    book: ModelBook,
    rng: Random,
    now: datetime,
) -> Row:
    entry = book[spec.model_id]
    request_id = uuid7_at(requested_at, rng)
    succeeded = outcome.status == RequestStatus.SUCCESS
    usage = _sample_usage(entry, spec, rng) if succeeded else None
    latency_ms = usage.latency_ms if usage else rng.randint(*outcome.latency_ms)
    completed_at = requested_at + timedelta(milliseconds=latency_ms)
    cost = (
        call_cost(entry, usage.input_tokens, usage.output_tokens, usage.cached)
        if usage
        else Decimal(0)
    )
    path = sample_cost_path(rng) if succeeded else CostPath.API_RESPONSE
    return {
        "request_id": request_id,
        "usage_origin": spec.usage_origin,
        "key_id": spec.key_id,
        "customer_id": spec.customer_id,
        "project_id": spec.project_id,
        "executed_by": spec.executed_by,
        "service_id": spec.service_id,
        "task_id": spec.task_id,
        "simulation_id": spec.simulation_id,
        "call_purpose": spec.call_purpose,
        "attempt_no": spec.attempt_no,
        "parent_request_id": spec.parent_request_id,
        "model_id": spec.model_id,
        "requested_model": entry.openrouter_id,
        "requested_provider": spec.requested_provider,
        "actual_model": entry.openrouter_id if succeeded else None,
        "actual_provider": _actual_provider(spec, entry, rng) if succeeded else None,
        "routing_policy": spec.routing_policy,
        "execution_config": (
            spec.execution_config
            if spec.execution_config is not None
            else EXECUTION_CONFIGS[spec.shape]
        ),
        "input_reference": spec.input_reference,
        "input_hash": spec.input_hash or sha256_hex(f"{request_id}:input"),
        "status": outcome.status,
        "error_type": outcome.error_type,
        "http_status": outcome.http_status,
        "error_message": outcome.error_message,
        "error_detail": outcome.error_detail,
        "finish_reason": FINISH_STOP if succeeded else None,
        "requested_at": requested_at,
        "completed_at": completed_at,
        "latency_ms": latency_ms,
        "external_generation_id": generation_id(requested_at, rng)
        if succeeded
        else None,
        "input_tokens": usage.input_tokens if usage else None,
        "output_tokens": usage.output_tokens if usage else None,
        "cached_tokens": usage.cached if usage else None,
        "cache_write_tokens": 0 if usage else None,
        "reasoning_tokens": usage.reasoning if usage else None,
        "usage_raw": _usage_raw(usage) if usage else None,
        **cost_fields(outcome, path, cost, completed_at, entry.price_id, now),
        "data_source": DataSource.MOCK,
    }


def _actual_provider(spec: CallSpec, entry: ModelEntry, rng: Random) -> str:
    if spec.requested_provider is not None:
        return spec.requested_provider
    return rng.choice(entry.profile.providers)


def _usage_raw(usage: _Usage) -> dict[str, JsonValue]:
    # 앱은 이 컬럼을 읽지 않는다. 금액은 cost_usd에만 두어 float을 섞지 않는다.
    return {
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
        "prompt_tokens_details": {"cached_tokens": usage.cached},
        "completion_tokens_details": {"reasoning_tokens": usage.reasoning},
    }

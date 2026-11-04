"""새 모델 발견과 기본 모델 비교(P-03). 새로 올라온 모델을 기록하고, 기본 모델과 같은 시나리오로 호출해 견준다."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DiscoveryStatus,
    ModelDiscovery,
    SkipReason,
    TestScenario,
)
from app.openrouter.lookup_result import LookupResult, ModelInfo
from app.openrouter.result import CallResult, CallStatus
from app.services import model_new
from app.services.base_model import find_base_model
from app.services.model_comparison import (
    Prices,
    estimate_max_cost,
    fits_budget,
    is_too_expensive,
)
from app.services.openrouter_catalog import OpenRouterUnavailableError
from app.services.provider_ranking import Workload
from app.services.simulation_input import build_messages, build_prompt_text

COMPARISON_SCENARIO_CODE = "PRODUCT_COPY"
COMPARISON_INPUT = (
    "상품명: 무선 노이즈캔슬링 이어폰\n"
    "특징: 배터리 30시간, 방수 IPX4, 블루투스 5.3, 화이트·블랙 두 가지 색상\n"
    "대상: 출퇴근하는 직장인"
)
DEFAULT_WORKLOAD = Workload(input_tokens=1000, output_tokens=500)
SPEND_WINDOW = timedelta(hours=24)

FetchModels = Callable[[], Awaitable[LookupResult[list[ModelInfo]]]]
CallModel = Callable[..., Awaitable[CallResult]]


@dataclass(frozen=True)
class DiscoveryConfig:
    daily_cap_usd: Decimal
    compare_enabled: bool
    window_days: int = 5
    base_days: int = 30
    max_price_ratio: Decimal = Decimal(5)
    max_tokens: int = 1024
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class DiscoverySummary:
    recorded: int
    compared: int
    skipped: int
    failed: int
    pending: int


def _prices_of(model: ModelInfo | None) -> Prices:
    if model is None:
        return Prices(input=None, output=None)
    return Prices(
        input=model.pricing.get("prompt"), output=model.pricing.get("completion")
    )


async def _record_new_models(
    session: AsyncSession, models: list[ModelInfo], *, now: datetime, days: int
) -> int:
    first_run = not await session.scalar(
        select(func.count(ModelDiscovery.discovery_id))
    )
    found = await model_new.find_new_models(
        session, models, now=now, days=days, limit=len(models) or 1
    )
    if not found.items:
        return 0
    status, reason = (
        (DiscoveryStatus.SKIPPED, SkipReason.INITIAL)
        if first_run
        else (DiscoveryStatus.PENDING, None)
    )
    inserted = await session.scalars(
        pg_insert(ModelDiscovery)
        .values(
            [
                {
                    "openrouter_model_id": entry.model.model_id,
                    "model_name": entry.model.name,
                    "openrouter_created_at": entry.created_at,
                    "discovered_at": now,
                    "status": status.value,
                    "skip_reason": reason.value if reason else None,
                }
                for entry in found.items
            ]
        )
        .on_conflict_do_nothing(index_elements=["openrouter_model_id"])
        .returning(ModelDiscovery.openrouter_model_id)
    )
    await session.commit()
    return len(inserted.all())


async def _spent_since(session: AsyncSession, since: datetime) -> Decimal:
    total = await session.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(ModelDiscovery.new_cost_usd, 0)
                    + func.coalesce(ModelDiscovery.base_cost_usd, 0)
                ),
                0,
            )
        ).where(ModelDiscovery.compared_at >= since)
    )
    return Decimal(total)


async def _skip(session: AsyncSession, discovery_id: int, reason: SkipReason) -> None:
    await session.execute(
        update(ModelDiscovery)
        .where(ModelDiscovery.discovery_id == discovery_id)
        .values(status=DiscoveryStatus.SKIPPED.value, skip_reason=reason.value)
    )
    await session.commit()


def _cost_of(result: CallResult) -> Decimal | None:
    return result.cost_usd if result.status == CallStatus.SUCCESS else None


def _latency_of(result: CallResult) -> int | None:
    return result.latency_ms if result.status == CallStatus.SUCCESS else None


async def run_discovery(
    session: AsyncSession,
    *,
    fetch_models: FetchModels,
    call_model: CallModel,
    now: datetime,
    config: DiscoveryConfig,
) -> DiscoverySummary:
    fetched = await fetch_models()
    if not fetched.ok or not fetched.data:
        raise OpenRouterUnavailableError("OpenRouter 모델 목록을 받지 못했습니다.")
    models = fetched.data
    by_id = {model.model_id: model for model in models}

    recorded = await _record_new_models(
        session, models, now=now, days=config.window_days
    )
    pending = (
        await session.execute(
            select(ModelDiscovery.discovery_id, ModelDiscovery.openrouter_model_id)
            .where(ModelDiscovery.status == DiscoveryStatus.PENDING)
            .order_by(ModelDiscovery.discovered_at, ModelDiscovery.discovery_id)
        )
    ).all()
    compared = skipped = failed = waiting = 0
    if not config.compare_enabled:
        return DiscoverySummary(recorded, 0, 0, 0, len(pending))

    base = await find_base_model(session, since=now - timedelta(days=config.base_days))
    scenario = await session.scalar(
        select(TestScenario).where(
            TestScenario.scenario_code == COMPARISON_SCENARIO_CODE,
            TestScenario.is_active,
        )
    )
    for discovery_id, model_id in pending:
        if base is None or scenario is None:
            waiting += 1
            continue

        prompt = build_prompt_text(scenario.prompt_template, COMPARISON_INPUT)
        max_tokens = min(
            config.max_tokens,
            scenario.default_execution_config.get("max_tokens", config.max_tokens),
        )
        base_prices = _prices_of(by_id.get(base.openrouter_model_id))
        new_prices = _prices_of(by_id.get(model_id))
        workload = (
            Workload(base.avg_input_tokens, base.avg_output_tokens)
            if base.avg_input_tokens and base.avg_output_tokens
            else DEFAULT_WORKLOAD
        )
        if is_too_expensive(
            base_prices, new_prices, workload, max_ratio=config.max_price_ratio
        ):
            await _skip(session, discovery_id, SkipReason.PRICE_TOO_HIGH)
            skipped += 1
            continue

        estimate = sum(
            estimate_max_cost(
                prompt_chars=len(prompt), max_tokens=max_tokens, prices=prices
            )
            or Decimal(0)
            for prices in (base_prices, new_prices)
        )
        spent = await _spent_since(session, now - SPEND_WINDOW)
        if not fits_budget(
            spent_today=spent,
            estimate=Decimal(estimate),
            daily_cap=config.daily_cap_usd,
        ):
            waiting += 1
            continue

        messages = build_messages(prompt)
        call: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout_seconds": config.timeout_seconds,
        }
        base_result, new_result = await asyncio.gather(
            call_model(
                request_id=uuid.uuid4(), model_id=base.openrouter_model_id, **call
            ),
            call_model(request_id=uuid.uuid4(), model_id=model_id, **call),
        )
        both_ok = all(
            result.status == CallStatus.SUCCESS for result in (base_result, new_result)
        )
        await session.execute(
            update(ModelDiscovery)
            .where(ModelDiscovery.discovery_id == discovery_id)
            .values(
                status=(
                    DiscoveryStatus.COMPARED if both_ok else DiscoveryStatus.FAILED
                ).value,
                base_model_id=base.model_id,
                compared_at=now,
                new_cost_usd=_cost_of(new_result),
                base_cost_usd=_cost_of(base_result),
                new_latency_ms=_latency_of(new_result),
                base_latency_ms=_latency_of(base_result),
            )
        )
        await session.commit()
        if both_ok:
            compared += 1
        else:
            failed += 1
    return DiscoverySummary(recorded, compared, skipped, failed, waiting)

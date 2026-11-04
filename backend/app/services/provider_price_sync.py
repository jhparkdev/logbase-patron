"""서버 업체별 단가를 가격 이력(model_prices)에 남긴다. 주기적으로 실행하는 관리 명령이 쓴다.

업체 행은 (모델, 업체)마다 현재 유효한 행이 하나다. 단가가 바뀌면 이전 행을 지우지 않고 기간만 닫은 뒤
새 행을 추가한다. 모델 대표가(execution_provider 가 NULL)는 건드리지 않는다.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelPrice, ModelRegistry, ModelStatus, PriceSource, PriceStatus
from app.openrouter.lookup_result import EndpointInfo, LookupResult
from app.services.model_registry import (
    PriceSnapshot,
    price_changed,
    snapshot_from_pricing,
)

FetchEndpoints = Callable[[str], Awaitable[LookupResult[list[EndpointInfo]]]]

# 사용 중이거나 시험 중인 모델만 본다. 비활성 모델의 업체 단가는 더 쓰지 않는다
SYNCED_STATUSES = (ModelStatus.ACTIVE, ModelStatus.TESTING)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncSummary:
    # 업체 목록을 물어본 모델 수
    models: int
    # 업체 목록을 받지 못한 모델 수
    failed_models: int
    added: int
    changed: int
    unchanged: int
    # 입력·출력 단가를 알 수 없어 저장하지 않은 업체 수
    skipped_providers: int


def _snapshot_of(row: ModelPrice) -> PriceSnapshot | None:
    if (
        row.price_status != PriceStatus.KNOWN
        or row.input_price_per_token is None
        or row.output_price_per_token is None
    ):
        return None
    return PriceSnapshot(
        input_price_per_token=row.input_price_per_token,
        output_price_per_token=row.output_price_per_token,
        cache_read_price_per_token=row.cache_read_price_per_token,
        cache_write_price_per_token=row.cache_write_price_per_token,
    )


def _new_row(
    model_id: int, endpoint: EndpointInfo, snapshot: PriceSnapshot, now: datetime
) -> ModelPrice:
    return ModelPrice(
        model_id=model_id,
        execution_provider=endpoint.provider_name,
        price_status=PriceStatus.KNOWN.value,
        input_price_per_token=snapshot.input_price_per_token,
        output_price_per_token=snapshot.output_price_per_token,
        cache_read_price_per_token=snapshot.cache_read_price_per_token,
        cache_write_price_per_token=snapshot.cache_write_price_per_token,
        # str()은 작은 값을 1E-7처럼 쓰므로 일반 숫자 표기로 남긴다
        raw_pricing={k: format(v, "f") for k, v in endpoint.pricing.items()},
        source=PriceSource.OPENROUTER_ENDPOINTS.value,
        effective_from=now,
        checked_at=now,
    )


async def sync_provider_prices(
    session: AsyncSession, fetch: FetchEndpoints, *, now: datetime
) -> SyncSummary:
    """등록된 모델마다 업체 단가를 받아 저장하고 모델 단위로 commit한다.

    한 모델을 받지 못해도 나머지는 계속한다. 받지 못한 모델은 이전 가격 이력을 그대로 둔다.
    """
    models = (
        await session.execute(
            select(ModelRegistry.model_id, ModelRegistry.openrouter_model_id)
            .where(ModelRegistry.status.in_(SYNCED_STATUSES))
            .order_by(ModelRegistry.model_id)
        )
    ).all()
    failed = added = changed = unchanged = skipped = 0
    for model_id, openrouter_model_id in models:
        result = await fetch(openrouter_model_id)
        if not result.ok or result.data is None:
            failed += 1
            logger.warning(
                "provider price sync: endpoints not read model_id=%s", model_id
            )
            continue
        current = {
            row.execution_provider: row
            for row in await session.scalars(
                select(ModelPrice).where(
                    ModelPrice.model_id == model_id,
                    ModelPrice.execution_provider.is_not(None),
                    ModelPrice.effective_to.is_(None),
                )
            )
        }
        for endpoint in result.data:
            snapshot = snapshot_from_pricing(endpoint.pricing)
            if snapshot is None:
                skipped += 1
                continue
            old = current.get(endpoint.provider_name)
            if old is not None and not price_changed(_snapshot_of(old), snapshot):
                unchanged += 1
                continue
            if old is not None:
                # 현재 행은 하나뿐이어야 하므로 새 행을 넣기 전에 이전 행의 기간을 닫는다
                old.effective_to = now
                await session.flush()
                changed += 1
            else:
                added += 1
            session.add(_new_row(model_id, endpoint, snapshot, now))
            await session.flush()
        await session.commit()
    return SyncSummary(
        models=len(models),
        failed_models=failed,
        added=added,
        changed=changed,
        unchanged=unchanged,
        skipped_providers=skipped,
    )

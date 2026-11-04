"""services/provider_price_sync.py 테스트. 서버 업체별 단가를 가격 이력 행으로 남기는 규칙을 본다."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelPrice, PriceSource
from app.openrouter.errors import ErrorType
from app.openrouter.lookup_result import EndpointInfo, LookupResult
from app.services.provider_price_sync import sync_provider_prices
from tests.db_helpers import Factory

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=1)


def endpoint(
    name: str = "DeepInfra",
    prompt: str | None = "0.000001",
    completion: str | None = "0.000002",
    **extra: str,
) -> EndpointInfo:
    pricing = {
        key: Decimal(value)
        for key, value in {
            "prompt": prompt,
            "completion": completion,
            **extra,
        }.items()
        if value is not None
    }
    return EndpointInfo(provider_name=name, status=0, pricing=pricing)


class FakeFetch:
    """모델 이름별로 정해 둔 업체 목록을 돌려준다. 정해 두지 않은 모델은 조회 실패다."""

    def __init__(self) -> None:
        self.by_model: dict[str, list[EndpointInfo]] = {}
        self.asked: list[str] = []

    async def __call__(
        self, openrouter_model_id: str
    ) -> LookupResult[list[EndpointInfo]]:
        self.asked.append(openrouter_model_id)
        if openrouter_model_id not in self.by_model:
            return LookupResult(error_type=ErrorType.NETWORK_ERROR)
        return LookupResult(data=self.by_model[openrouter_model_id], http_status=200)


async def provider_rows(session: AsyncSession, model_id: int) -> list[ModelPrice]:
    return list(
        await session.scalars(
            select(ModelPrice)
            .where(
                ModelPrice.model_id == model_id,
                ModelPrice.execution_provider.is_not(None),
            )
            .order_by(ModelPrice.price_id)
        )
    )


async def test_a_new_provider_price_is_added_as_a_current_row(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    fetch = FakeFetch()
    fetch.by_model[model["openrouter_model_id"]] = [
        endpoint(input_cache_read="0.0000001", input_cache_write="0.0000012")
    ]

    summary = await sync_provider_prices(db_session, fetch, now=NOW)

    [row] = await provider_rows(db_session, model["model_id"])
    assert row.execution_provider == "DeepInfra"
    assert row.price_status == "KNOWN"
    assert row.source == PriceSource.OPENROUTER_ENDPOINTS
    assert row.input_price_per_token == Decimal("0.000001")
    assert row.output_price_per_token == Decimal("0.000002")
    assert row.cache_read_price_per_token == Decimal("0.0000001")
    assert row.cache_write_price_per_token == Decimal("0.0000012")
    assert (row.effective_from, row.effective_to, row.checked_at) == (NOW, None, NOW)
    assert (summary.added, summary.changed, summary.unchanged) == (1, 0, 0)


async def test_the_same_price_is_not_stored_again(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    fetch = FakeFetch()
    fetch.by_model[model["openrouter_model_id"]] = [endpoint()]
    await sync_provider_prices(db_session, fetch, now=NOW)

    summary = await sync_provider_prices(db_session, fetch, now=LATER)

    assert len(await provider_rows(db_session, model["model_id"])) == 1
    assert (summary.added, summary.changed, summary.unchanged) == (0, 0, 1)


async def test_a_changed_price_closes_the_old_row_and_adds_a_new_one(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    fetch = FakeFetch()
    fetch.by_model[model["openrouter_model_id"]] = [endpoint()]
    await sync_provider_prices(db_session, fetch, now=NOW)
    fetch.by_model[model["openrouter_model_id"]] = [endpoint(completion="0.000003")]

    summary = await sync_provider_prices(db_session, fetch, now=LATER)

    old, new = await provider_rows(db_session, model["model_id"])
    # 이전 가격은 지우지 않고 기간만 닫는다
    assert old.output_price_per_token == Decimal("0.000002")
    assert old.effective_to == LATER
    assert new.output_price_per_token == Decimal("0.000003")
    assert (new.effective_from, new.effective_to) == (LATER, None)
    assert (summary.added, summary.changed, summary.unchanged) == (0, 1, 0)


async def test_each_provider_has_its_own_current_row(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    fetch = FakeFetch()
    fetch.by_model[model["openrouter_model_id"]] = [
        endpoint("DeepInfra"),
        endpoint("Novita", prompt="0.0000005"),
    ]

    await sync_provider_prices(db_session, fetch, now=NOW)

    rows = await provider_rows(db_session, model["model_id"])
    assert {row.execution_provider for row in rows} == {"DeepInfra", "Novita"}


async def test_the_model_representative_price_is_left_alone(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    representative = await factory.model_price(model_id=model["model_id"])
    fetch = FakeFetch()
    fetch.by_model[model["openrouter_model_id"]] = [endpoint(prompt="0.5")]

    await sync_provider_prices(db_session, fetch, now=NOW)

    row = await db_session.get(ModelPrice, representative["price_id"])
    assert row is not None
    assert row.execution_provider is None
    assert row.effective_to is None
    assert row.input_price_per_token == Decimal("0.000001")


async def test_a_provider_without_a_usable_price_is_skipped(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model(status="ACTIVE")
    fetch = FakeFetch()
    fetch.by_model[model["openrouter_model_id"]] = [
        endpoint("NoOutput", completion=None),
        endpoint("Negative", prompt="-0.000001"),
    ]

    summary = await sync_provider_prices(db_session, fetch, now=NOW)

    assert await provider_rows(db_session, model["model_id"]) == []
    assert (summary.added, summary.skipped_providers) == (0, 2)


async def test_a_model_that_cannot_be_read_is_counted_and_the_rest_continue(
    db_session: AsyncSession, factory: Factory
) -> None:
    broken = await factory.model(status="ACTIVE")
    working = await factory.model(status="ACTIVE")
    fetch = FakeFetch()
    fetch.by_model[working["openrouter_model_id"]] = [endpoint()]

    summary = await sync_provider_prices(db_session, fetch, now=NOW)

    assert len(await provider_rows(db_session, working["model_id"])) == 1
    assert await provider_rows(db_session, broken["model_id"]) == []
    assert (summary.models, summary.failed_models, summary.added) == (2, 1, 1)


async def test_inactive_models_are_not_asked(
    db_session: AsyncSession, factory: Factory
) -> None:
    inactive = await factory.model(status="INACTIVE")
    fetch = FakeFetch()

    summary = await sync_provider_prices(db_session, fetch, now=NOW)

    assert fetch.asked == []
    assert summary.models == 0
    assert inactive["status"] == "INACTIVE"

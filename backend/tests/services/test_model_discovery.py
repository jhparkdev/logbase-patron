"""services/model_discovery.py 테스트. 새 모델 기록, 사전 거름, 비용 상한, 실제 호출 비교를 가짜 호출로 본다."""

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.openrouter.errors import ErrorType
from app.openrouter.lookup_result import LookupResult, ModelInfo
from app.openrouter.result import CallResult, CallStatus, CostSource, CostStatus
from app.services.model_discovery import (
    COMPARISON_SCENARIO_CODE,
    DiscoveryConfig,
    run_discovery,
)
from tests.api.model_helpers import info
from tests.db_helpers import T0, Factory

NOW = T0 + timedelta(days=100)
RECENT = NOW - timedelta(days=1)
BASE_PRICING = {"prompt": Decimal("0.000001"), "completion": Decimal("0.000002")}
CONFIG = DiscoveryConfig(daily_cap_usd=Decimal(1), compare_enabled=True)


@dataclass
class FakeOpenRouter:
    """정해 둔 모델 목록과 호출 결과를 돌려주고, 어느 모델을 불렀는지 기록한다."""

    models: list[ModelInfo]
    results: dict[str, CallResult] = field(default_factory=dict)
    called: list[str] = field(default_factory=list)

    async def fetch(self) -> LookupResult[list[ModelInfo]]:
        return LookupResult(data=self.models)

    async def call(self, **kwargs: Any) -> CallResult:
        self.called.append(kwargs["model_id"])
        return self.results[kwargs["model_id"]]


def reply(
    model_id: str,
    *,
    cost: str | None = "0.001",
    latency_ms: int = 1000,
    status: CallStatus = CallStatus.SUCCESS,
) -> CallResult:
    return CallResult(
        status=status,
        error_type=None if status == CallStatus.SUCCESS else ErrorType.UNKNOWN_ERROR,
        requested_model=model_id,
        cost_usd=None if cost is None else Decimal(cost),
        cost_status=CostStatus.UNKNOWN if cost is None else CostStatus.CONFIRMED,
        cost_source=None if cost is None else CostSource.API_RESPONSE,
        started_at=NOW,
        finished_at=NOW,
        latency_ms=latency_ms,
    )


def new_model(model_id: str = "a/new", **fields: Any) -> ModelInfo:
    return info(
        model_id,
        created_at=RECENT,
        pricing=fields.pop("pricing", BASE_PRICING),
        **fields,
    )


async def setup_base(factory: Factory) -> dict[str, Any]:
    """고객 호출이 있는 기본 모델, 비교용 시나리오, 이미 기록이 있는 상태를 만든다."""
    base = await factory.model(openrouter_model_id="a/base")
    customer = await factory.customer()
    key = await factory.api_key(
        owner_type="CUSTOMER", customer_id=customer["customer_id"]
    )
    await factory.ai_request(
        usage_origin="CUSTOMER_SERVICE",
        customer_id=customer["customer_id"],
        key_id=key["key_id"],
        model_id=base["model_id"],
        status="SUCCESS",
        requested_at=RECENT,
    )
    await factory.scenario(
        scenario_code=COMPARISON_SCENARIO_CODE,
        prompt_template="상품 정보로 문구를 쓰세요.\n{{product_info}}",
        default_execution_config={"max_tokens": 512},
    )
    await factory.model_discovery(
        openrouter_model_id="a/old", status="SKIPPED", skip_reason="INITIAL"
    )
    return base


async def discovery_of(session: AsyncSession, model_id: str) -> dict[str, Any]:
    row = await session.execute(
        text("SELECT * FROM model_discoveries WHERE openrouter_model_id = :id"),
        {"id": model_id},
    )
    return dict(row.mappings().one())


def fake(*extra: ModelInfo, **results: CallResult) -> FakeOpenRouter:
    base = info("a/base", pricing=BASE_PRICING)
    return FakeOpenRouter(models=[base, *extra], results=results)


async def run(session: AsyncSession, openrouter: FakeOpenRouter, config=CONFIG):
    return await run_discovery(
        session,
        fetch_models=openrouter.fetch,
        call_model=openrouter.call,
        now=NOW,
        config=config,
    )


async def test_처음_실행이면_이미_올라와_있던_모델은_비교하지_않고_기록만_한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    await db_session.execute(text("DELETE FROM model_discoveries"))
    openrouter = fake(new_model())

    summary = await run(db_session, openrouter)

    row = await discovery_of(db_session, "a/new")
    assert (row["status"], row["skip_reason"]) == ("SKIPPED", "INITIAL")
    assert openrouter.called == []
    assert summary.recorded == 1


async def test_새_모델을_기록하고_같은_모델은_다시_기록하지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    openrouter = fake(
        new_model(), **{"a/new": reply("a/new"), "a/base": reply("a/base")}
    )

    first = await run(db_session, openrouter)
    second = await run(db_session, openrouter)

    assert first.recorded == 1
    assert second.recorded == 0
    count = await db_session.scalar(
        text(
            "SELECT count(*) FROM model_discoveries WHERE openrouter_model_id = 'a/new'"
        )
    )
    assert count == 1


async def test_기본_모델과_같은_시나리오로_두_모델을_부르고_비용과_시간을_남긴다(
    db_session: AsyncSession, factory: Factory
) -> None:
    base = await setup_base(factory)
    openrouter = fake(
        new_model(),
        **{
            "a/new": reply("a/new", cost="0.0005", latency_ms=800),
            "a/base": reply("a/base", cost="0.001", latency_ms=1000),
        },
    )

    summary = await run(db_session, openrouter)

    row = await discovery_of(db_session, "a/new")
    assert row["status"] == "COMPARED"
    assert row["base_model_id"] == base["model_id"]
    assert row["compared_at"] == NOW
    assert (row["new_cost_usd"], row["base_cost_usd"]) == (
        Decimal("0.0005"),
        Decimal("0.001"),
    )
    assert (row["new_latency_ms"], row["base_latency_ms"]) == (800, 1000)
    assert sorted(openrouter.called) == ["a/base", "a/new"]
    assert summary.compared == 1


async def test_비교를_꺼_두면_기록만_하고_호출하지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    openrouter = fake(new_model())
    config = DiscoveryConfig(daily_cap_usd=Decimal(1), compare_enabled=False)

    await run(db_session, openrouter, config)

    assert (await discovery_of(db_session, "a/new"))["status"] == "PENDING"
    assert openrouter.called == []


async def test_기본_모델이_없으면_호출하지_않고_다음에_다시_시도하도록_남긴다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.model_discovery(
        openrouter_model_id="a/old", status="SKIPPED", skip_reason="INITIAL"
    )
    await factory.scenario(scenario_code=COMPARISON_SCENARIO_CODE)
    openrouter = fake(new_model())

    summary = await run(db_session, openrouter)

    assert (await discovery_of(db_session, "a/new"))["status"] == "PENDING"
    assert openrouter.called == []
    assert summary.pending == 1


async def test_비교할_시나리오가_없으면_호출하지_않고_다음에_다시_시도하도록_남긴다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    await db_session.execute(text("DELETE FROM test_scenarios"))
    openrouter = fake(new_model())

    await run(db_session, openrouter)

    assert (await discovery_of(db_session, "a/new"))["status"] == "PENDING"
    assert openrouter.called == []


async def test_단가가_기본_모델보다_너무_비싸면_호출하지_않고_이유를_남긴다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    pricey = {"prompt": Decimal("0.0001"), "completion": Decimal("0.0002")}
    openrouter = fake(new_model(pricing=pricey))

    await run(db_session, openrouter)

    row = await discovery_of(db_session, "a/new")
    assert (row["status"], row["skip_reason"]) == ("SKIPPED", "PRICE_TOO_HIGH")
    assert openrouter.called == []


async def test_새_모델의_단가를_모르면_호출하지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    openrouter = fake(new_model(pricing={}))

    await run(db_session, openrouter)

    row = await discovery_of(db_session, "a/new")
    assert (row["status"], row["skip_reason"]) == ("SKIPPED", "PRICE_TOO_HIGH")


async def test_하루_비용_상한에_닿으면_호출하지_않고_다음에_다시_시도하도록_남긴다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    openrouter = fake(new_model())
    config = DiscoveryConfig(daily_cap_usd=Decimal("0.0001"), compare_enabled=True)

    summary = await run(db_session, openrouter, config)

    assert (await discovery_of(db_session, "a/new"))["status"] == "PENDING"
    assert openrouter.called == []
    assert summary.pending == 1


async def test_최근_24시간에_쓴_비교_비용이_상한을_채우면_더_부르지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    base = await setup_base(factory)
    await factory.model_discovery(
        openrouter_model_id="a/earlier",
        status="COMPARED",
        compared_at=NOW - timedelta(hours=2),
        base_model_id=base["model_id"],
        new_cost_usd=Decimal("0.5"),
        base_cost_usd=Decimal("0.5"),
    )
    openrouter = fake(new_model())

    await run(db_session, openrouter)

    assert (await discovery_of(db_session, "a/new"))["status"] == "PENDING"
    assert openrouter.called == []


async def test_한쪽_호출이_실패하면_실패로_남기고_성공한_쪽의_값만_저장한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    openrouter = fake(
        new_model(),
        **{
            "a/new": reply("a/new", cost=None, status=CallStatus.FAILED),
            "a/base": reply("a/base", cost="0.001"),
        },
    )

    summary = await run(db_session, openrouter)

    row = await discovery_of(db_session, "a/new")
    assert row["status"] == "FAILED"
    assert row["new_cost_usd"] is None
    assert row["base_cost_usd"] == Decimal("0.001")
    assert summary.failed == 1


async def test_비용을_모르는_성공_호출은_비용을_0이_아닌_빈_값으로_남긴다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await setup_base(factory)
    openrouter = fake(
        new_model(),
        **{"a/new": reply("a/new", cost=None), "a/base": reply("a/base")},
    )

    await run(db_session, openrouter)

    row = await discovery_of(db_session, "a/new")
    assert row["status"] == "COMPARED"
    assert row["new_cost_usd"] is None

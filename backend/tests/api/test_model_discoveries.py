"""GET /api/models/openrouter/discoveries 테스트. 새 모델과 기본 모델 비교 결과를 알림 목록으로 돌려준다."""

from datetime import timedelta
from decimal import Decimal
from typing import Any

from httpx import AsyncClient

from tests.db_helpers import T0, Factory

URL = "/api/models/openrouter/discoveries"


async def compared(factory: Factory, **values: Any) -> dict[str, Any]:
    base = await factory.model(display_name="기본 모델")
    return dict(
        await factory.model_discovery(
            status="COMPARED",
            compared_at=T0,
            base_model_id=base["model_id"],
            **values,
        )
    )


async def test_비교를_마친_모델은_증감률과_저렴함_빠름을_함께_준다(
    client: AsyncClient, factory: Factory
) -> None:
    await compared(
        factory,
        openrouter_model_id="a/new",
        model_name="A: New",
        base_cost_usd=Decimal("0.001"),
        new_cost_usd=Decimal("0.0005"),
        base_latency_ms=1000,
        new_latency_ms=1200,
    )

    response = await client.get(URL)

    [item] = response.json()["items"]
    assert item["openrouter_model_id"] == "a/new"
    assert item["name"] == "A: New"
    assert item["status"] == "COMPARED"
    assert item["base_model_name"] == "기본 모델"
    assert item["cost_change_pct"] == "-50.0"
    assert item["latency_change_pct"] == "20.0"
    assert item["cheaper"] is True
    assert item["faster"] is False


async def test_넘어간_모델은_이유를_주고_비교_값은_비어_있다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model_discovery(
        openrouter_model_id="a/skipped", status="SKIPPED", skip_reason="PRICE_TOO_HIGH"
    )

    [item] = (await client.get(URL)).json()["items"]

    assert item["status"] == "SKIPPED"
    assert item["skip_reason"] == "PRICE_TOO_HIGH"
    assert item["base_model_name"] is None
    assert item["cost_change_pct"] is None
    assert item["cheaper"] is None


async def test_비용을_모르면_증감률과_저렴함을_판단하지_않는다(
    client: AsyncClient, factory: Factory
) -> None:
    await compared(
        factory,
        base_cost_usd=Decimal("0.001"),
        new_cost_usd=None,
        base_latency_ms=1000,
        new_latency_ms=500,
    )

    [item] = (await client.get(URL)).json()["items"]

    assert item["new_cost_usd"] is None
    assert item["cost_change_pct"] is None
    assert item["cheaper"] is None
    assert item["faster"] is True


async def test_이름을_모르면_모델_ID를_이름으로_준다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model_discovery(openrouter_model_id="a/nameless")

    [item] = (await client.get(URL)).json()["items"]

    assert item["name"] == "a/nameless"
    assert item["status"] == "PENDING"


async def test_최근_발견한_순서로_limit개까지_준다(
    client: AsyncClient, factory: Factory
) -> None:
    for days, model_id in enumerate(["a/oldest", "a/middle", "a/latest"]):
        await factory.model_discovery(
            openrouter_model_id=model_id, discovered_at=T0 + timedelta(days=days)
        )

    body = (await client.get(URL, params={"limit": 2})).json()

    assert [item["openrouter_model_id"] for item in body["items"]] == [
        "a/latest",
        "a/middle",
    ]


async def test_limit이_범위를_벗어나면_거절한다(client: AsyncClient) -> None:
    for limit in (0, 51):
        assert (await client.get(URL, params={"limit": limit})).status_code == 422


async def test_기록이_없으면_빈_목록을_준다(client: AsyncClient) -> None:
    assert (await client.get(URL)).json() == {"items": []}

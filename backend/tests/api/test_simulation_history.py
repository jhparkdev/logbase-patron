"""GET /api/simulations (S-08) 테스트. 거른 결과 전체를 고정 순서로 주고 정렬·페이지는 화면이 한다."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import simulation_history
from tests.api.simulation_helpers import CREATE
from tests.db_helpers import T0, Factory

# 고정 시각 T0 는 KST 10월 1일 09:00 이다. 기본 기간은 KST 9월 2일 0시(UTC 9월 1일 15:00)부터다
DEFAULT_PERIOD_START = T0 - timedelta(hours=9) - timedelta(days=29)
ONE_MICROSECOND = timedelta(microseconds=1)


async def run_at(factory: Factory, requested_at: object, **values: Any) -> str:
    row = await factory.simulation_run(requested_at=requested_at, **values)
    return str(row["simulation_id"])


async def listed_ids(client: AsyncClient, **params: Any) -> list[str]:
    response = await client.get(CREATE, params=params)
    assert response.status_code == 200, response.text
    return [item["simulation_id"] for item in response.json()["items"]]


@pytest.mark.usefixtures("signed_in")
async def test_the_default_period_is_the_last_30_kst_days_newest_first(
    client: AsyncClient, factory: Factory
) -> None:
    await run_at(factory, DEFAULT_PERIOD_START - ONE_MICROSECOND)
    first_moment = await run_at(factory, DEFAULT_PERIOD_START)
    latest = await run_at(factory, T0)

    assert await listed_ids(client) == [latest, first_moment]


@pytest.mark.usefixtures("signed_in")
async def test_the_end_date_covers_its_whole_kst_day(
    client: AsyncClient, factory: Factory
) -> None:
    # KST 10월 1일의 마지막 순간은 UTC 10월 1일 15:00 직전이다
    next_kst_midnight = T0 + timedelta(hours=15)
    last_moment = await run_at(factory, next_kst_midnight - ONE_MICROSECOND)
    await run_at(factory, next_kst_midnight)

    ids = await listed_ids(client, start_date="2026-10-01", end_date="2026-10-01")

    assert ids == [last_moment]


@pytest.mark.usefixtures("signed_in")
async def test_runs_requested_at_the_same_moment_keep_a_fixed_order(
    client: AsyncClient, factory: Factory
) -> None:
    # 화면이 다시 정렬하기 전에도 부를 때마다 같은 순서여야 한다. 같은 시각이면 실행 ID 내림차순이다
    ids = [await run_at(factory, T0) for _ in range(3)]

    assert await listed_ids(client) == sorted(ids, key=uuid.UUID, reverse=True)


@pytest.mark.usefixtures("signed_in")
async def test_filters_narrow_the_history(
    client: AsyncClient, factory: Factory
) -> None:
    scenario = await factory.scenario()
    model = await factory.model()
    by_scenario = await run_at(
        factory, T0, test_type="SCENARIO", scenario_id=scenario["scenario_id"]
    )
    by_status = await run_at(factory, T0, status="FAILED")
    by_model = await run_at(factory, T0)
    await factory.simulation_result(
        simulation_id=uuid.UUID(by_model), model_id=model["model_id"]
    )

    assert await listed_ids(client, scenario_id=scenario["scenario_id"]) == [
        by_scenario
    ]
    assert await listed_ids(client, status="FAILED") == [by_status]
    assert await listed_ids(client, model_id=model["model_id"]) == [by_model]


@pytest.mark.usefixtures("signed_in")
async def test_a_run_older_than_the_default_period_is_found_by_its_id(
    client: AsyncClient, factory: Factory
) -> None:
    old = await run_at(factory, T0 - timedelta(days=200))
    await run_at(factory, T0)

    assert await listed_ids(client, simulation_id=old) == [old]


@pytest.mark.usefixtures("signed_in")
async def test_a_list_item_is_the_same_summary_the_detail_shows(
    client: AsyncClient, factory: Factory
) -> None:
    # 목록과 상세가 같은 뷰에서 나오므로 같은 실행이면 합계도 같다
    simulation_id = await run_at(factory, T0, status="SUCCESS", completed_at=T0)
    run = uuid.UUID(simulation_id)
    for slot_no, cost in [(1, Decimal("0.000123")), (2, Decimal("0.000002"))]:
        request = await factory.ai_request(
            usage_origin="SIMULATION",
            simulation_id=run,
            status="SUCCESS",
            cost_status="CONFIRMED",
            cost_usd=cost,
        )
        await factory.simulation_result(
            simulation_id=run, request_id=request["request_id"], slot_no=slot_no
        )

    listed = (await client.get(CREATE)).json()["items"]
    detail = (await client.get(f"{CREATE}/{simulation_id}")).json()["summary"]

    assert listed == [detail]
    assert detail["confirmed_cost_usd"] == "0.000125000000000000"


@pytest.mark.usefixtures("signed_in")
async def test_an_empty_history_is_an_empty_list(client: AsyncClient) -> None:
    response = await client.get(CREATE)

    assert response.json() == {"items": [], "total": 0, "truncated": False}


@pytest.mark.usefixtures("signed_in")
async def test_beyond_the_limit_the_newest_are_kept_and_the_cut_is_reported(
    client: AsyncClient, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(simulation_history, "MAX_HISTORY_ITEMS", 2)
    await run_at(factory, T0 - timedelta(hours=2))
    middle = await run_at(factory, T0 - timedelta(hours=1))
    latest = await run_at(factory, T0)

    body = (await client.get(CREATE)).json()

    assert [item["simulation_id"] for item in body["items"]] == [latest, middle]
    assert (body["total"], body["truncated"]) == (3, True)


@pytest.mark.usefixtures("signed_in")
async def test_exactly_the_limit_is_not_reported_as_cut(
    client: AsyncClient, factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(simulation_history, "MAX_HISTORY_ITEMS", 2)
    for hours in (1, 0):
        await run_at(factory, T0 - timedelta(hours=hours))

    body = (await client.get(CREATE)).json()

    assert (len(body["items"]), body["total"], body["truncated"]) == (2, 2, False)


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"start_date": "2026-10-01"}, "PERIOD_INCOMPLETE"),
        (
            {"start_date": "2026-10-02", "end_date": "2026-10-01"},
            "PERIOD_START_AFTER_END",
        ),
        ({"start_date": "2025-01-01", "end_date": "2026-01-02"}, "PERIOD_TOO_LONG"),
    ],
)
async def test_an_invalid_period_is_refused(
    client: AsyncClient, params: dict[str, str], code: str
) -> None:
    response = await client.get(CREATE, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == code


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize("params", [{"sort": "requested_at"}, {"page": "2"}])
async def test_sorting_and_paging_parameters_are_refused(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(CREATE, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"

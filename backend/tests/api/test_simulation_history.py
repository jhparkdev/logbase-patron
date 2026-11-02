"""GET /api/simulations (S-08) 테스트. 거른 결과를 서버가 정렬하고 한 페이지씩 준다."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient

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
    # 같은 값이면 실행 ID 내림차순으로 순서를 고정한다. 그래야 페이지를 넘겨도 겹치거나 빠지지 않는다
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

    # 목록 행은 요약에 "지금 선택할 수 없는 모델 수"만 더한다
    assert [
        {k: v for k, v in item.items() if k != "inactive_model_count"}
        for item in listed
    ] == [detail]
    assert detail["confirmed_cost_usd"] == "0.000125000000000000"
    assert Decimal(detail["total_cost_usd"]) == Decimal("0.000125")


@pytest.mark.usefixtures("signed_in")
async def test_each_row_counts_the_models_that_can_no_longer_be_chosen(
    client: AsyncClient, factory: Factory
) -> None:
    # 재실행하려면 바꿔야 하는 모델 수다. 같은 모델을 Provider 만 바꿔 두 칸에 넣었어도 한 개로 센다
    run = uuid.UUID(await run_at(factory, T0))
    active = await factory.model(status="ACTIVE")
    retired = await factory.model(status="INACTIVE")
    for slot_no, model in [(1, active), (2, retired), (3, retired)]:
        await factory.simulation_result(
            simulation_id=run,
            model_id=model["model_id"],
            slot_no=slot_no,
            execution_provider=f"provider-{slot_no}",
        )

    item = (await client.get(CREATE)).json()["items"][0]

    assert item["inactive_model_count"] == 1


@pytest.mark.usefixtures("signed_in")
async def test_a_row_whose_models_are_all_selectable_counts_zero(
    client: AsyncClient, factory: Factory
) -> None:
    run = uuid.UUID(await run_at(factory, T0))
    await factory.simulation_result(
        simulation_id=run, model_id=(await factory.model(status="ACTIVE"))["model_id"]
    )

    assert (await client.get(CREATE)).json()["items"][0]["inactive_model_count"] == 0


@pytest.mark.usefixtures("signed_in")
async def test_an_empty_history_is_an_empty_list(client: AsyncClient) -> None:
    response = await client.get(CREATE)

    assert response.json() == {"items": [], "total": 0}


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize(
    ("page", "expected"),
    [(1, [0, 1]), (2, [2]), (3, [])],
    ids=["first", "last", "past"],
)
async def test_pages_split_the_sorted_history(
    client: AsyncClient, factory: Factory, page: int, expected: list[int]
) -> None:
    newest_first = [await run_at(factory, T0 - timedelta(hours=h)) for h in range(3)]

    body = (await client.get(CREATE, params={"page": page, "page_size": 2})).json()

    assert [item["simulation_id"] for item in body["items"]] == [
        newest_first[i] for i in expected
    ]
    # 범위를 넘은 페이지도 오류가 아니라 빈 목록이고, 전체 건수는 그대로다
    assert body["total"] == 3


@pytest.mark.usefixtures("signed_in")
async def test_the_default_page_holds_ten(
    client: AsyncClient, factory: Factory
) -> None:
    for minutes in range(11):
        await run_at(factory, T0 - timedelta(minutes=minutes))

    body = (await client.get(CREATE)).json()

    assert (len(body["items"]), body["total"]) == (10, 11)


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize("direction", ["asc", "desc"])
async def test_the_history_is_sorted_by_the_chosen_column(
    client: AsyncClient, factory: Factory, direction: str
) -> None:
    by_count = {
        count: await run_at(factory, T0, model_count=count) for count in (3, 2, 4)
    }

    ids = await listed_ids(client, sort="modelCount", direction=direction)

    ascending = [by_count[2], by_count[3], by_count[4]]
    assert ids == (ascending if direction == "asc" else ascending[::-1])


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize("direction", ["asc", "desc"])
async def test_empty_values_go_last_in_either_direction(
    client: AsyncClient, factory: Factory, direction: str
) -> None:
    # 직접 작성 실행은 시나리오 코드가 없다. 방향을 바꿔도 맨 위로 올라오지 않는다
    scenario = await factory.scenario()
    custom = await run_at(factory, T0)
    from_scenario = await run_at(
        factory, T0, test_type="SCENARIO", scenario_id=scenario["scenario_id"]
    )

    ids = await listed_ids(client, sort="scenario", direction=direction)

    assert ids == [from_scenario, custom]


async def run_with_costs(factory: Factory, *slots: tuple[str, Decimal | None]) -> str:
    """칸마다 (비용 상태, 금액)을 준 실행. 추정 비용은 가격 근거가 있어야 기록된다(DB 제약)."""
    run = await factory.simulation_run(requested_at=T0, status="PARTIAL_SUCCESS")
    price_id = (await factory.model_price())["price_id"]
    for slot_no, (cost_status, cost) in enumerate(slots, start=1):
        request = await factory.ai_request(
            usage_origin="SIMULATION",
            simulation_id=run["simulation_id"],
            status="SUCCESS",
            cost_status=cost_status,
            cost_usd=cost,
            price_id=price_id if cost_status == "ESTIMATED" else None,
        )
        await factory.simulation_result(
            simulation_id=run["simulation_id"],
            request_id=request["request_id"],
            slot_no=slot_no,
        )
    return str(run["simulation_id"])


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize("direction", ["asc", "desc"])
async def test_the_history_is_sorted_by_the_total_of_confirmed_and_estimated_costs(
    client: AsyncClient, factory: Factory, direction: str
) -> None:
    # 한쪽 합계만 있어도 그 금액 자리에 선다. 금액을 아는 호출이 없는 실행만 0 이 아니라 맨 뒤다
    confirmed_only = await run_with_costs(factory, ("CONFIRMED", Decimal("0.003")))
    estimated_only = await run_with_costs(factory, ("ESTIMATED", Decimal("0.002")))
    both = await run_with_costs(
        factory,
        ("CONFIRMED", Decimal("0.0005")),
        ("ESTIMATED", Decimal("0.0005")),
        ("UNKNOWN", None),
    )
    unknown_only = await run_with_costs(factory, ("UNKNOWN", None))

    ids = await listed_ids(client, sort="totalCost", direction=direction)

    ascending = [both, estimated_only, confirmed_only]
    known = ascending if direction == "asc" else ascending[::-1]
    assert ids == [*known, unknown_only]


@pytest.mark.usefixtures("signed_in")
async def test_sorting_applies_before_paging(
    client: AsyncClient, factory: Factory
) -> None:
    # 오래된 순 첫 페이지는 전체에서 가장 오래된 실행이다. 잘린 목록 안에서만 정렬하지 않는다
    newest_first = [await run_at(factory, T0 - timedelta(hours=h)) for h in range(3)]

    ids = await listed_ids(client, direction="asc", page=1, page_size=1)

    assert ids == [newest_first[-1]]


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
@pytest.mark.parametrize(
    "params",
    [{"sort": "prompt_text"}, {"direction": "up"}, {"page": "0"}, {"page_size": "101"}],
)
async def test_sorting_and_paging_values_outside_the_contract_are_refused(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(CREATE, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"

"""P-01 집계 테스트. 경계값은 만든 행으로, 합계는 seed 기대값으로 검증한다.

seed 기대값은 집계 코드를 거치지 않고 생성기(app.mock_data)가 만든 행을 직접 더해 구했다.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.schemas.models import SortOrder
from app.schemas.usage import (
    CustomerRowSort,
    CustomerRowsQuery,
    RequestRowSort,
    RequestRowsQuery,
)
from app.services import aggregation
from app.services.aggregation import UsageFilter, change_pct, previous_period
from app.services.budget_policy import WARNING_PCT, BudgetStatus
from app.services.simulation_period import DateRange
from tests.db_helpers import Factory

OCTOBER = DateRange(date(2026, 10, 1), date(2026, 10, 31))
OCTOBER_FILTER = UsageFilter(period=OCTOBER)
OCTOBER_1ST = date(2026, 10, 1)
# KST 10월 1일 0시 = UTC 9월 30일 15시
KST_OCTOBER_START = datetime(2026, 9, 30, 15, tzinfo=UTC)
NOVEMBER_START = datetime(2026, 10, 31, 15, tzinfo=UTC)
ONE_MICROSECOND = timedelta(microseconds=1)
IN_OCTOBER = datetime(2026, 10, 10, 3, tzinfo=UTC)
LATE_PAGE_SIZE = 100


def six_places(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), ROUND_HALF_UP)


def one_place(value: Decimal | None) -> Decimal:
    assert value is not None
    return value.quantize(Decimal("0.1"), ROUND_HALF_UP)


async def customer_call(factory: Factory, **values: Any) -> dict[str, Any]:
    row = await factory.ai_request(
        **{"usage_origin": "CUSTOMER_SERVICE", "requested_at": IN_OCTOBER, **values}
    )
    return dict(row)


def confirmed(amount: str) -> dict[str, Any]:
    return {"cost_status": "CONFIRMED", "cost_usd": Decimal(amount)}


async def estimated(factory: Factory, amount: str) -> dict[str, Any]:
    price = await factory.model_price()
    return {
        "cost_status": "ESTIMATED",
        "cost_usd": Decimal(amount),
        "price_id": price["price_id"],
    }


@pytest.fixture
async def seeded(db_session: AsyncSession) -> None:
    await cli.apply_seed(await db_session.connection())


# 순수 함수


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (Decimal(12), Decimal(10), Decimal("20.00")),
        (Decimal(5), Decimal(10), Decimal("-50.00")),
        (Decimal(10), Decimal(10), Decimal("0.00")),
        (Decimal(10), Decimal(0), None),
        (Decimal(0), Decimal(0), None),
    ],
)
def test_change_pct_is_none_when_there_is_nothing_to_compare(
    current: Decimal, previous: Decimal, expected: Decimal | None
) -> None:
    assert change_pct(current, previous) == expected


def test_previous_period_is_the_same_length_right_before() -> None:
    assert previous_period(OCTOBER) == DateRange(date(2026, 8, 31), date(2026, 9, 30))


def test_previous_period_of_a_single_day_is_the_day_before() -> None:
    day = DateRange(date(2026, 3, 1), date(2026, 3, 1))

    assert previous_period(day) == DateRange(date(2026, 2, 28), date(2026, 2, 28))


# Mock 기대값


@pytest.mark.usefixtures("seeded")
async def test_summary_matches_the_mock_totals_for_october(
    db_session: AsyncSession,
) -> None:
    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)

    assert summary.call_count == 1461
    assert summary.success_count == 1416
    assert six_places(summary.confirmed_cost_usd) == Decimal("6.997544")
    assert six_places(summary.estimated_cost_usd) == Decimal("0.070391")
    assert summary.unknown_cost_count == 42
    assert summary.input_tokens + summary.output_tokens == 5_184_779


@pytest.mark.usefixtures("seeded")
async def test_customer_rows_match_the_mock_totals_by_customer(
    db_session: AsyncSession,
) -> None:
    page = await aggregation.list_customer_rows(
        db_session,
        OCTOBER_FILTER,
        CustomerRowsQuery(page_size=LATE_PAGE_SIZE),
    )

    totals: dict[str | None, list[Any]] = {}
    for row in page.items:
        total = totals.setdefault(row.customer_name, [0, Decimal(0), 0])
        total[0] += row.call_count
        total[1] += row.confirmed_cost_usd + row.estimated_cost_usd
        total[2] += row.unknown_cost_count

    by_name = {name: (t[0], six_places(t[1]), t[2]) for name, t in totals.items()}
    assert by_name == {
        "로웰린 스튜디오": (623, Decimal("4.193431"), 20),
        "에이븐전자몰": (313, Decimal("0.259847"), 8),
        "뮤렌 코스메틱": (322, Decimal("2.383118"), 7),
        "솔레담 푸드": (137, Decimal("0.028476"), 7),
        "모뉴하우스": (54, Decimal("0.043043"), 0),
        None: (12, Decimal("0.160021"), 0),
    }


@pytest.mark.usefixtures("seeded")
async def test_customer_budgets_match_the_mock_budget_table(
    db_session: AsyncSession,
) -> None:
    over = await aggregation.customer_detail(db_session, 1, OCTOBER_1ST)
    normal = await aggregation.customer_detail(db_session, 2, OCTOBER_1ST)
    warning = await aggregation.customer_detail(db_session, 3, OCTOBER_1ST)
    unset = await aggregation.customer_detail(db_session, 5, OCTOBER_1ST)

    assert over is not None
    assert normal is not None
    assert warning is not None
    assert unset is not None
    assert over.budget.status == BudgetStatus.OVER
    assert one_place(over.budget.usage_pct) == Decimal("110.4")
    assert one_place(over.budget.confirmed_usage_pct) == Decimal("108.8")
    assert six_places(over.budget.remaining_usd) == Decimal("-0.393431")
    assert over.budget.unknown_cost_count == 20
    assert normal.budget.status == BudgetStatus.NORMAL
    assert one_place(normal.budget.usage_pct) == Decimal("52.0")
    assert one_place(normal.budget.confirmed_usage_pct) == Decimal("51.7")
    assert normal.budget.unknown_cost_count == 8
    assert warning.budget.status == BudgetStatus.WARNING
    assert one_place(warning.budget.usage_pct) == Decimal("88.3")
    assert six_places(warning.budget.remaining_usd) == Decimal("0.316882")
    assert unset.budget.status == BudgetStatus.UNSET


@pytest.mark.usefixtures("seeded")
async def test_customer_budget_for_september_uses_only_september_usage(
    db_session: AsyncSession,
) -> None:
    detail = await aggregation.customer_detail(db_session, 1, date(2026, 9, 1))

    assert detail is not None
    assert six_places(detail.budget.used_usd) == Decimal("2.904613")
    assert one_place(detail.budget.usage_pct) == Decimal("76.4")


@pytest.mark.usefixtures("seeded")
async def test_every_block_adds_up_to_the_same_totals(db_session: AsyncSession) -> None:
    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)
    trend = await aggregation.daily_trend(db_session, OCTOBER_FILTER)
    rows = await aggregation.list_customer_rows(
        db_session, OCTOBER_FILTER, CustomerRowsQuery(page_size=LATE_PAGE_SIZE)
    )
    calls = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery(page_size=LATE_PAGE_SIZE)
    )
    all_calls = list(calls.items)
    for page in range(2, calls.total // LATE_PAGE_SIZE + 2):
        next_page = await aggregation.list_requests(
            db_session,
            OCTOBER_FILTER,
            RequestRowsQuery(page=page, page_size=LATE_PAGE_SIZE),
        )
        all_calls += next_page.items

    assert (
        summary.call_count
        == sum(point.call_count for point in trend.items)
        == sum(row.call_count for row in rows.items)
        == calls.total
        == len(all_calls)
    )
    assert (
        summary.confirmed_cost_usd
        == sum(point.confirmed_cost_usd for point in trend.items)
        == sum(row.confirmed_cost_usd for row in rows.items)
        == sum(c.cost_usd for c in all_calls if c.cost_status == "CONFIRMED")
    )
    assert (
        summary.estimated_cost_usd
        == sum(point.estimated_cost_usd for point in trend.items)
        == sum(row.estimated_cost_usd for row in rows.items)
        == sum(c.cost_usd for c in all_calls if c.cost_status == "ESTIMATED")
    )
    assert (
        summary.unknown_cost_count
        == sum(point.unknown_cost_count for point in trend.items)
        == sum(row.unknown_cost_count for row in rows.items)
        == sum(1 for c in all_calls if c.cost_status == "UNKNOWN")
    )
    # 작업은 자정을 넘길 수 있어 일별 합계와는 비교하지 않는다
    assert summary.task_count == sum(row.task_count for row in rows.items)


# 고객 사용만 집계


async def test_only_customer_service_calls_are_counted(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(factory, **confirmed("1"))
    for origin in ("INTERNAL_DEVELOPMENT", "SIMULATION", "SYSTEM_TEST"):
        await factory.ai_request(
            usage_origin=origin, requested_at=IN_OCTOBER, **confirmed("100")
        )

    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)
    calls = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery()
    )

    assert summary.call_count == 1
    assert summary.confirmed_cost_usd == Decimal(1)
    assert calls.total == 1


# 비용 상태


async def test_unknown_cost_is_counted_and_never_added_as_zero(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(factory, status="TIMEOUT", error_type="TIMEOUT_ERROR")
    await customer_call(factory, **confirmed("2"))
    await customer_call(factory, **await estimated(factory, "3"))

    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)

    assert summary.call_count == 3
    assert summary.confirmed_cost_usd == Decimal(2)
    assert summary.estimated_cost_usd == Decimal(3)
    assert summary.unknown_cost_count == 1
    assert summary.timeout_count == 1


async def test_no_calls_are_zero_counts_and_null_changes(
    db_session: AsyncSession,
) -> None:
    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)

    assert summary.call_count == 0
    assert summary.confirmed_cost_usd == Decimal(0)
    assert summary.unknown_cost_count == 0
    assert summary.call_change_pct is None


# 작업 건수와 호출 수


async def test_task_count_is_distinct_and_retries_count_as_calls(
    db_session: AsyncSession, factory: Factory
) -> None:
    service = await factory.service()
    customer = await factory.customer()
    task = await factory.task(
        usage_origin="CUSTOMER_SERVICE",
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
    )
    for _ in range(3):
        await customer_call(
            factory,
            customer_id=customer["customer_id"],
            service_id=service["service_id"],
            task_id=task["task_id"],
        )
    await customer_call(factory, customer_id=customer["customer_id"])

    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)

    assert summary.task_count == 1
    assert summary.call_count == 4


# 기간 경계


async def test_kst_period_boundaries_are_exact(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(
        factory, requested_at=KST_OCTOBER_START - ONE_MICROSECOND, **confirmed("1")
    )
    await customer_call(factory, requested_at=KST_OCTOBER_START, **confirmed("2"))
    await customer_call(
        factory, requested_at=NOVEMBER_START - ONE_MICROSECOND, **confirmed("4")
    )
    await customer_call(factory, requested_at=NOVEMBER_START, **confirmed("8"))

    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)

    assert summary.confirmed_cost_usd == Decimal(6)


async def test_trend_puts_calls_on_their_kst_day_and_fills_empty_days(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(
        factory, requested_at=KST_OCTOBER_START - ONE_MICROSECOND, **confirmed("1")
    )
    await customer_call(factory, requested_at=KST_OCTOBER_START, **confirmed("2"))
    period = DateRange(date(2026, 9, 30), date(2026, 10, 2))

    trend = await aggregation.daily_trend(db_session, UsageFilter(period=period))

    assert [point.date for point in trend.items] == [
        date(2026, 9, 30),
        date(2026, 10, 1),
        date(2026, 10, 2),
    ]
    assert [point.confirmed_cost_usd for point in trend.items] == [
        Decimal(1),
        Decimal(2),
        Decimal(0),
    ]
    assert trend.items[2].call_count == 0


async def test_summary_compares_with_the_previous_period(
    db_session: AsyncSession, factory: Factory
) -> None:
    previous_day = IN_OCTOBER - timedelta(days=31)
    await customer_call(factory, requested_at=previous_day, **confirmed("10"))
    await customer_call(factory, **confirmed("12"))
    await customer_call(factory, status="CANCELLED")

    summary = await aggregation.summarize(db_session, OCTOBER_FILTER)

    assert summary.comparison_start_date == date(2026, 8, 31)
    assert summary.comparison_end_date == date(2026, 9, 30)
    assert summary.call_change_pct == Decimal("100.00")
    assert summary.confirmed_cost_change_pct == Decimal("20.00")
    assert summary.estimated_cost_change_pct is None


# 필터


async def test_filters_separate_customers_services_and_models(
    db_session: AsyncSession, factory: Factory
) -> None:
    first = await factory.customer()
    second = await factory.customer()
    service = await factory.service()
    model = await factory.model()
    await customer_call(factory, customer_id=first["customer_id"], **confirmed("1"))
    await customer_call(factory, customer_id=second["customer_id"], **confirmed("2"))
    await customer_call(factory, service_id=service["service_id"], **confirmed("4"))
    await customer_call(factory, model_id=model["model_id"], **confirmed("8"))

    by_customer = UsageFilter(period=OCTOBER, customer_id=first["customer_id"])
    by_service = UsageFilter(period=OCTOBER, service_id=service["service_id"])
    by_model = UsageFilter(period=OCTOBER, model_id=model["model_id"])

    assert (
        await aggregation.summarize(db_session, by_customer)
    ).confirmed_cost_usd == Decimal(1)
    assert (
        await aggregation.summarize(db_session, by_service)
    ).confirmed_cost_usd == Decimal(4)
    assert (
        await aggregation.summarize(db_session, by_model)
    ).confirmed_cost_usd == Decimal(8)


async def test_options_list_customer_services_and_used_models_only(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer(name="고객 가")
    facing = await factory.service(name="AI PDP", service_type="CUSTOMER_FACING")
    await factory.service(name="내부 도구", service_type="INTERNAL")
    used = await factory.model(display_name="사용한 모델")
    await factory.model(display_name="쓰지 않은 모델")
    internal_only = await factory.model(display_name="내부에서만 쓴 모델")
    await customer_call(factory, model_id=used["model_id"])
    await factory.ai_request(model_id=internal_only["model_id"])

    options = await aggregation.list_options(db_session)

    assert {(o.id, o.name) for o in options.customers} >= {
        (customer["customer_id"], "고객 가")
    }
    assert (facing["service_id"], "AI PDP") in {
        (o.id, o.name) for o in options.services
    }
    assert "내부 도구" not in {o.name for o in options.services}
    assert [o.name for o in options.models] == ["사용한 모델"]


# 고객 표


async def rows_of(db_session: AsyncSession, **query: Any) -> list[Any]:
    page = await aggregation.list_customer_rows(
        db_session, OCTOBER_FILTER, CustomerRowsQuery(**query)
    )
    return page.items


async def test_one_customer_with_two_services_has_two_rows_with_the_same_budget(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    first = await factory.service(name="가 서비스")
    second = await factory.service(name="나 서비스")
    customer_id = customer["customer_id"]
    await factory.budget(
        scope_type="CUSTOMER", customer_id=customer_id, monthly_amount_usd=Decimal(10)
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=first["service_id"],
        **confirmed("1"),
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=second["service_id"],
        **confirmed("3"),
    )

    rows = await rows_of(db_session, sort=CustomerRowSort.SERVICE, order=SortOrder.ASC)

    assert [row.service_name for row in rows] == ["가 서비스", "나 서비스"]
    assert [row.confirmed_cost_usd for row in rows] == [Decimal(1), Decimal(3)]
    assert rows[0].budget == rows[1].budget
    assert rows[0].budget.used_usd == Decimal(4)
    assert rows[0].budget.usage_pct == Decimal("40.00")


async def test_budget_ignores_service_filter_and_query_period(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    service = await factory.service()
    other = await factory.service()
    customer_id = customer["customer_id"]
    await factory.budget(
        scope_type="CUSTOMER", customer_id=customer_id, monthly_amount_usd=Decimal(10)
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=service["service_id"],
        requested_at=datetime(2026, 10, 2, tzinfo=UTC),
        **confirmed("1"),
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=other["service_id"],
        requested_at=datetime(2026, 10, 20, tzinfo=UTC),
        **confirmed("4"),
    )
    narrow = UsageFilter(
        period=DateRange(date(2026, 10, 25), date(2026, 10, 31)),
        service_id=service["service_id"],
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=service["service_id"],
        requested_at=datetime(2026, 10, 26, tzinfo=UTC),
        **confirmed("2"),
    )

    page = await aggregation.list_customer_rows(db_session, narrow, CustomerRowsQuery())

    assert page.items[0].confirmed_cost_usd == Decimal(2)
    assert page.items[0].budget.used_usd == Decimal(7)
    assert page.items[0].budget.month == date(2026, 10, 1)


async def test_budget_month_uses_kst_boundary(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    customer_id = customer["customer_id"]
    await factory.budget(scope_type="CUSTOMER", customer_id=customer_id)
    await customer_call(
        factory,
        customer_id=customer_id,
        requested_at=KST_OCTOBER_START - ONE_MICROSECOND,
        **confirmed("1"),
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        requested_at=KST_OCTOBER_START,
        **confirmed("2"),
    )

    detail = await aggregation.customer_detail(db_session, customer_id, OCTOBER_1ST)

    assert detail is not None
    assert detail.budget.used_usd == Decimal(2)


async def test_budget_outside_its_effective_months_is_unset(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    await factory.budget(
        scope_type="CUSTOMER",
        customer_id=customer["customer_id"],
        effective_from_month=date(2026, 11, 1),
    )

    detail = await aggregation.customer_detail(
        db_session, customer["customer_id"], OCTOBER_1ST
    )

    assert detail is not None
    assert detail.budget.status == BudgetStatus.UNSET
    assert detail.budget.usage_pct is None


async def test_unknown_customer_stays_in_an_unclassified_row(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(factory, customer_id=None, **confirmed("1"))

    rows = await rows_of(db_session)

    assert rows[0].customer_id is None
    assert rows[0].customer_name is None
    assert rows[0].budget.status == BudgetStatus.UNSET


async def test_unset_budget_sorts_last_in_both_directions(
    db_session: AsyncSession, factory: Factory
) -> None:
    small = await factory.customer(name="작은 예산")
    large = await factory.customer(name="큰 예산")
    none = await factory.customer(name="예산 없음")
    for customer, amount in ((small, 10), (large, 20)):
        await factory.budget(
            scope_type="CUSTOMER",
            customer_id=customer["customer_id"],
            monthly_amount_usd=Decimal(amount),
        )
    for customer in (small, large, none):
        await customer_call(factory, customer_id=customer["customer_id"])

    for sort in (
        CustomerRowSort.BUDGET,
        CustomerRowSort.USAGE,
        CustomerRowSort.STATUS,
    ):
        ascending = await rows_of(db_session, sort=sort, order=SortOrder.ASC)
        descending = await rows_of(db_session, sort=sort, order=SortOrder.DESC)
        assert ascending[-1].customer_name == "예산 없음"
        assert descending[-1].customer_name == "예산 없음"

    ascending = await rows_of(
        db_session, sort=CustomerRowSort.BUDGET, order=SortOrder.ASC
    )
    assert [row.customer_name for row in ascending[:2]] == ["작은 예산", "큰 예산"]


async def test_customer_table_defaults_to_highest_confirmed_cost(
    db_session: AsyncSession, factory: Factory
) -> None:
    low = await factory.customer(name="낮음")
    high = await factory.customer(name="높음")
    await customer_call(factory, customer_id=low["customer_id"], **confirmed("1"))
    await customer_call(factory, customer_id=high["customer_id"], **confirmed("5"))

    rows = await rows_of(db_session)

    assert [row.customer_name for row in rows] == ["높음", "낮음"]


async def test_customer_preview_picks_top_five_then_sorts_inside(
    db_session: AsyncSession, factory: Factory
) -> None:
    for amount in range(1, 8):
        customer = await factory.customer(name=f"고객{amount}")
        await customer_call(
            factory, customer_id=customer["customer_id"], **confirmed(str(amount))
        )

    page = await aggregation.list_customer_rows(
        db_session,
        OCTOBER_FILTER,
        CustomerRowsQuery(
            preview=True, sort=CustomerRowSort.CONFIRMED, order=SortOrder.ASC
        ),
    )

    # 비용이 가장 큰 5개를 고른 뒤 그 안에서 오름차순이다
    assert [row.confirmed_cost_usd for row in page.items] == [
        Decimal(3),
        Decimal(4),
        Decimal(5),
        Decimal(6),
        Decimal(7),
    ]
    assert page.total == 7


async def test_customer_table_pages_after_sorting(
    db_session: AsyncSession, factory: Factory
) -> None:
    for amount in range(1, 4):
        customer = await factory.customer()
        await customer_call(
            factory, customer_id=customer["customer_id"], **confirmed(str(amount))
        )

    page = await aggregation.list_customer_rows(
        db_session, OCTOBER_FILTER, CustomerRowsQuery(page=2, page_size=2)
    )

    assert page.total == 3
    assert [row.confirmed_cost_usd for row in page.items] == [Decimal(1)]


# 호출 표


async def test_request_row_has_model_tokens_and_task_type(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer(name="고객 가")
    service = await factory.service(name="AI PDP")
    task = await factory.task(
        usage_origin="CUSTOMER_SERVICE",
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
        task_type="문서 요약",
    )
    await customer_call(
        factory,
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
        task_id=task["task_id"],
        requested_model="vendor/requested",
        actual_model="vendor/actual",
        input_tokens=10,
        output_tokens=5,
        status="SUCCESS",
        **confirmed("0.02"),
    )

    page = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery()
    )
    row = page.items[0]

    assert row.customer_name == "고객 가"
    assert row.service_name == "AI PDP"
    assert row.model == "vendor/actual"
    assert row.task_type == "문서 요약"
    assert row.tokens == 15
    assert row.cost_usd == Decimal("0.02")


async def test_request_row_falls_back_to_requested_model_and_null_tokens(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(factory, requested_model="vendor/requested", input_tokens=10)

    page = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery()
    )

    assert page.items[0].model == "vendor/requested"
    assert page.items[0].tokens is None
    assert page.items[0].cost_usd is None


@pytest.mark.parametrize(
    ("task_type", "label"),
    [
        ("PRODUCT_DESCRIPTION", "상품 설명 생성"),
        ("CATALOG_SUMMARY", "카탈로그 요약"),
        ("IMAGE_ANALYSIS", "이미지 분석"),
        ("NEW_INTERNAL_CODE", "기타"),  # 모르는 코드를 화면에 그대로 내보내지 않는다
    ],
)
async def test_request_row_has_a_display_name_for_its_task_type(
    db_session: AsyncSession, factory: Factory, task_type: str, label: str
) -> None:
    service = await factory.service()
    task = await factory.task(
        usage_origin="CUSTOMER_SERVICE",
        service_id=service["service_id"],
        task_type=task_type,
    )
    await customer_call(
        factory, service_id=service["service_id"], task_id=task["task_id"]
    )

    page = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery()
    )

    assert page.items[0].task_type == task_type
    assert page.items[0].task_type_label == label


async def test_request_without_a_task_has_no_task_type_label(
    db_session: AsyncSession, factory: Factory
) -> None:
    await customer_call(factory)

    page = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery()
    )

    assert page.items[0].task_type_label is None


async def test_task_type_sorts_by_the_name_shown_on_screen_with_missing_last(
    db_session: AsyncSession, factory: Factory
) -> None:
    service = await factory.service()
    for task_type in ("PRODUCT_DESCRIPTION", "CATALOG_SUMMARY", "IMAGE_ANALYSIS"):
        task = await factory.task(
            usage_origin="CUSTOMER_SERVICE",
            service_id=service["service_id"],
            task_type=task_type,
        )
        await customer_call(
            factory, service_id=service["service_id"], task_id=task["task_id"]
        )
    await customer_call(factory)

    page = await aggregation.list_requests(
        db_session,
        OCTOBER_FILTER,
        RequestRowsQuery(sort=RequestRowSort.TASK_TYPE, order=SortOrder.ASC),
    )

    assert [row.task_type_label for row in page.items] == [
        "상품 설명 생성",
        "이미지 분석",
        "카탈로그 요약",
        None,
    ]


async def test_korean_names_sort_in_dictionary_order(
    db_session: AsyncSession, factory: Factory
) -> None:
    # 기본 정렬 규칙(en_US.utf8)은 띄어쓰기가 든 한글을 가나다순으로 정렬하지 않는다
    names = ["상품 고객", "이미지 고객", "카탈로그 고객"]
    for name in reversed(names):
        customer = await factory.customer(name=name)
        service = await factory.service(
            name=name.replace("고객", "서비스"), service_type="CUSTOMER_FACING"
        )
        await customer_call(
            factory,
            customer_id=customer["customer_id"],
            service_id=service["service_id"],
        )

    by_customer = await aggregation.list_requests(
        db_session,
        OCTOBER_FILTER,
        RequestRowsQuery(sort=RequestRowSort.CUSTOMER, order=SortOrder.ASC),
    )
    by_service = await aggregation.list_requests(
        db_session,
        OCTOBER_FILTER,
        RequestRowsQuery(sort=RequestRowSort.SERVICE, order=SortOrder.DESC),
    )
    options = await aggregation.list_options(db_session)

    assert [row.customer_name for row in by_customer.items] == names
    assert [row.service_name for row in by_service.items] == [
        "카탈로그 서비스",
        "이미지 서비스",
        "상품 서비스",
    ]
    assert [o.name for o in options.customers if o.name in names] == names


@pytest.mark.parametrize("order", [SortOrder.ASC, SortOrder.DESC])
async def test_unknown_cost_sorts_last_in_both_directions(
    db_session: AsyncSession, factory: Factory, order: SortOrder
) -> None:
    await customer_call(factory)
    await customer_call(factory, **confirmed("1"))
    await customer_call(factory, **confirmed("2"))

    page = await aggregation.list_requests(
        db_session,
        OCTOBER_FILTER,
        RequestRowsQuery(sort=RequestRowSort.COST, order=order),
    )

    costs = [row.cost_usd for row in page.items]
    assert costs[-1] is None
    expected = [Decimal(1), Decimal(2)]
    assert costs[:2] == (expected if order == SortOrder.ASC else expected[::-1])


async def test_requests_default_to_newest_first_with_a_stable_order(
    db_session: AsyncSession, factory: Factory
) -> None:
    older = await customer_call(factory, requested_at=IN_OCTOBER)
    newer = await customer_call(factory, requested_at=IN_OCTOBER + timedelta(minutes=1))

    page = await aggregation.list_requests(
        db_session, OCTOBER_FILTER, RequestRowsQuery()
    )

    assert [row.request_id for row in page.items] == [
        newer["request_id"],
        older["request_id"],
    ]


async def test_request_preview_keeps_the_latest_20_then_sorts_inside(
    db_session: AsyncSession, factory: Factory
) -> None:
    oldest = await customer_call(
        factory, requested_at=IN_OCTOBER - timedelta(days=1), **confirmed("999")
    )
    for minute in range(20):
        await customer_call(
            factory,
            requested_at=IN_OCTOBER + timedelta(minutes=minute),
            **confirmed("1"),
        )

    page = await aggregation.list_requests(
        db_session,
        OCTOBER_FILTER,
        RequestRowsQuery(preview=True, sort=RequestRowSort.COST, order=SortOrder.DESC),
    )

    assert len(page.items) == 20
    assert oldest["request_id"] not in {row.request_id for row in page.items}
    assert page.total == 21


# 고객 상세


async def test_detail_splits_usage_by_service_with_budget_share(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer(name="누리")
    first = await factory.service(name="가 서비스")
    second = await factory.service(name="나 서비스")
    customer_id = customer["customer_id"]
    await factory.budget(
        scope_type="CUSTOMER", customer_id=customer_id, monthly_amount_usd=Decimal(20)
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=first["service_id"],
        **confirmed("2"),
    )
    await customer_call(
        factory,
        customer_id=customer_id,
        service_id=second["service_id"],
        **await estimated(factory, "3"),
    )
    await customer_call(
        factory, customer_id=customer_id, service_id=second["service_id"]
    )

    detail = await aggregation.customer_detail(db_session, customer_id, OCTOBER_1ST)

    assert detail is not None
    assert detail.customer_name == "누리"
    assert detail.call_count == 3
    assert detail.confirmed_cost_usd == Decimal(2)
    assert detail.estimated_cost_usd == Decimal(3)
    assert detail.unknown_cost_count == 1
    shares = {s.service_name: s.budget_share_pct for s in detail.services}
    assert shares == {"가 서비스": Decimal("10.00"), "나 서비스": Decimal("15.00")}
    unknown = {s.service_name: s.unknown_cost_count for s in detail.services}
    assert unknown == {"가 서비스": 0, "나 서비스": 1}


async def test_detail_without_budget_has_no_share(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    await customer_call(factory, customer_id=customer["customer_id"], **confirmed("2"))

    detail = await aggregation.customer_detail(
        db_session, customer["customer_id"], OCTOBER_1ST
    )

    assert detail is not None
    assert detail.services[0].budget_share_pct is None
    assert detail.budget.effective_from_month is None


async def test_detail_service_total_adds_confirmed_and_estimated_but_not_unknown(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    service = await factory.service()
    same = {"customer_id": customer["customer_id"], "service_id": service["service_id"]}
    await customer_call(factory, **same, **confirmed("2"))
    await customer_call(factory, **same, **await estimated(factory, "3"))
    await customer_call(factory, **same)

    detail = await aggregation.customer_detail(
        db_session, customer["customer_id"], OCTOBER_1ST
    )

    assert detail is not None
    [usage] = detail.services
    assert usage.total_cost_usd == Decimal(5)
    assert usage.unknown_cost_count == 1


async def test_detail_service_totals_add_up_to_the_budget_usage(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()
    customer_id = customer["customer_id"]
    for name, amount in (("가 서비스", "1.5"), ("나 서비스", "2.25")):
        service = await factory.service(name=name)
        await customer_call(
            factory,
            customer_id=customer_id,
            service_id=service["service_id"],
            **confirmed(amount),
        )
        await customer_call(
            factory,
            customer_id=customer_id,
            service_id=service["service_id"],
            **await estimated(factory, amount),
        )

    detail = await aggregation.customer_detail(db_session, customer_id, OCTOBER_1ST)

    assert detail is not None
    services_total = sum((s.total_cost_usd for s in detail.services), Decimal(0))
    assert services_total == detail.budget.used_usd == Decimal("7.5")


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (Decimal("-0.01"), BudgetStatus.NORMAL),
        (Decimal(0), BudgetStatus.WARNING),
        (Decimal("0.01"), BudgetStatus.WARNING),
    ],
    ids=["기준 바로 전", "기준과 같음", "기준 바로 후"],
)
async def test_detail_budget_sends_the_warning_threshold_its_status_uses(
    db_session: AsyncSession, factory: Factory, offset: Decimal, expected: BudgetStatus
) -> None:
    customer = await factory.customer()
    customer_id = customer["customer_id"]
    # 예산을 100달러로 두면 사용액이 곧 사용률(%)이다
    await factory.budget(
        scope_type="CUSTOMER", customer_id=customer_id, monthly_amount_usd=Decimal(100)
    )
    await customer_call(
        factory, customer_id=customer_id, **confirmed(str(WARNING_PCT + offset))
    )

    detail = await aggregation.customer_detail(db_session, customer_id, OCTOBER_1ST)

    assert detail is not None
    assert detail.budget.warning_threshold_pct == WARNING_PCT
    assert detail.budget.status == expected


async def test_detail_without_budget_still_sends_the_warning_threshold(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer()

    detail = await aggregation.customer_detail(
        db_session, customer["customer_id"], OCTOBER_1ST
    )

    assert detail is not None
    assert detail.budget.status == BudgetStatus.UNSET
    assert detail.budget.warning_threshold_pct == WARNING_PCT


async def test_detail_of_an_unknown_customer_is_none(db_session: AsyncSession) -> None:
    assert await aggregation.customer_detail(db_session, 987654, OCTOBER_1ST) is None

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CostStatus, RequestStatus, UsageOrigin
from app.schemas.internal_requests import InternalRequestSort, InternalRequestsQuery
from app.schemas.models import SortOrder
from app.services.aggregation import REQUEST_PREVIEW_ROWS
from app.services.internal_requests import list_options, list_requests
from app.services.internal_usage import summarize
from app.services.simulation_period import DateRange
from tests.db_helpers import Factory
from tests.internal_budget_helpers import IN_OCTOBER, UNKNOWN_COST, internal_call

PERIOD = DateRange(date(2026, 10, 1), date(2026, 10, 31))


def query(**values: object) -> InternalRequestsQuery:
    return InternalRequestsQuery.model_validate(values)


# ---------------------------------------------------------------
# 어떤 호출이 나오는가
# ---------------------------------------------------------------
async def test_내부_출처_호출만_나오고_고객_호출은_나오지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    for origin in ("INTERNAL_DEVELOPMENT", "SIMULATION", "SYSTEM_TEST"):
        await internal_call(factory, usage_origin=origin)
    await internal_call(factory, usage_origin="CUSTOMER_SERVICE")

    page = await list_requests(db_session, PERIOD, query(sort="requestedAt"))

    assert page.total == 3
    assert {row.usage_origin for row in page.items} == {
        UsageOrigin.INTERNAL_DEVELOPMENT,
        UsageOrigin.SIMULATION,
        UsageOrigin.SYSTEM_TEST,
    }


@pytest.mark.parametrize(
    ("requested_at", "expected"),
    [
        (datetime(2026, 9, 30, 14, 59, 59, 999999, tzinfo=UTC), 0),
        (datetime(2026, 9, 30, 15, 0, tzinfo=UTC), 1),
        (datetime(2026, 10, 31, 14, 59, 59, 999999, tzinfo=UTC), 1),
        (datetime(2026, 10, 31, 15, 0, tzinfo=UTC), 0),
    ],
    ids=["시작 직전", "시작 정각", "말일 마지막", "다음 날 0시"],
)
async def test_기간_경계는_KST_기준이다(
    db_session: AsyncSession, factory: Factory, requested_at: datetime, expected: int
) -> None:
    await internal_call(factory, requested_at=requested_at)

    page = await list_requests(db_session, PERIOD, query())

    assert page.total == expected
    assert len(page.items) == expected


async def test_프로젝트_서비스_모델로_거른다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    service = await factory.service()
    model = await factory.model()
    target = await internal_call(
        factory,
        project_id=project["project_id"],
        service_id=service["service_id"],
        model_id=model["model_id"],
    )
    await internal_call(factory)

    for filters in (
        {"project_id": project["project_id"]},
        {"service_id": service["service_id"]},
        {"model_id": model["model_id"]},
    ):
        page = await list_requests(db_session, PERIOD, query(**filters))

        assert [row.request_id for row in page.items] == [target["request_id"]]
        assert page.total == 1


# ---------------------------------------------------------------
# 한 행의 값
# ---------------------------------------------------------------
async def test_행에_프로젝트_서비스_모델_토큰_비용_상태가_들어_있다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    service = await factory.service(name="시뮬레이터")
    await internal_call(
        factory,
        project_id=project["project_id"],
        service_id=service["service_id"],
        requested_model="vendor/requested",
        actual_model="vendor/actual",
        input_tokens=10,
        output_tokens=5,
        status="SUCCESS",
        cost_usd=Decimal("0.02"),
    )

    row = (await list_requests(db_session, PERIOD, query())).items[0]

    assert row.usage_origin == UsageOrigin.INTERNAL_DEVELOPMENT
    assert row.project_id == project["project_id"]
    assert row.project_name == "알파"
    assert row.service_name == "시뮬레이터"
    assert row.model == "vendor/actual"
    assert row.tokens == 15
    assert row.cost_usd == Decimal("0.02")
    assert row.cost_status == CostStatus.CONFIRMED
    assert row.status == RequestStatus.SUCCESS
    assert row.error_type is None


async def test_실제_모델이_없으면_요청한_모델을_보여_주고_토큰을_모르면_null이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await internal_call(factory, requested_model="vendor/requested", input_tokens=10)

    row = (await list_requests(db_session, PERIOD, query())).items[0]

    assert row.model == "vendor/requested"
    assert row.tokens is None


async def test_비용을_모르는_호출은_비용이_null이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await internal_call(factory, **UNKNOWN_COST)

    row = (await list_requests(db_session, PERIOD, query())).items[0]

    assert row.cost_usd is None
    assert row.cost_status == CostStatus.UNKNOWN


@pytest.mark.parametrize(
    ("task_type", "label"),
    [
        ("PRODUCT_DESCRIPTION", "상품 설명 생성"),
        ("CATALOG_SUMMARY", "카탈로그 요약"),
        ("IMAGE_ANALYSIS", "이미지 분석"),
        ("NEW_INTERNAL_CODE", "기타"),  # 모르는 코드를 화면에 그대로 내보내지 않는다
    ],
)
async def test_작업_유형은_화면에_보여_줄_이름을_함께_준다(
    db_session: AsyncSession, factory: Factory, task_type: str, label: str
) -> None:
    task = await factory.task(task_type=task_type)
    await internal_call(factory, task_id=task["task_id"])

    row = (await list_requests(db_session, PERIOD, query())).items[0]

    assert row.task_type == task_type
    assert row.task_type_label == label


async def test_작업이_없는_호출은_작업_유형이_null이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await internal_call(factory)

    row = (await list_requests(db_session, PERIOD, query())).items[0]

    assert row.task_id is None
    assert row.task_type is None
    assert row.task_type_label is None


# ---------------------------------------------------------------
# 정렬
# ---------------------------------------------------------------
async def test_기본은_최신순이고_같은_시각이면_순서가_고정이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    older = await internal_call(factory, requested_at=IN_OCTOBER)
    newer = await internal_call(factory, requested_at=IN_OCTOBER + timedelta(minutes=1))

    page = await list_requests(db_session, PERIOD, query())

    assert [row.request_id for row in page.items] == [
        newer["request_id"],
        older["request_id"],
    ]


@pytest.mark.parametrize("order", [SortOrder.ASC, SortOrder.DESC])
async def test_비용_정렬은_비용을_모르는_호출을_방향과_상관없이_맨_뒤에_둔다(
    db_session: AsyncSession, factory: Factory, order: SortOrder
) -> None:
    await internal_call(factory, cost_usd=Decimal(2))
    await internal_call(factory, **UNKNOWN_COST)
    await internal_call(factory, cost_usd=Decimal(1))

    page = await list_requests(
        db_session, PERIOD, query(sort=InternalRequestSort.COST, order=order)
    )

    costs = [row.cost_usd for row in page.items]
    assert costs[-1] is None
    expected = [Decimal(1), Decimal(2)]
    assert costs[:2] == (expected if order == SortOrder.ASC else expected[::-1])


@pytest.mark.parametrize(
    ("sort", "order", "expected"),
    [
        (InternalRequestSort.PROJECT, SortOrder.ASC, ["가", "나"]),
        (InternalRequestSort.PROJECT, SortOrder.DESC, ["나", "가"]),
        (InternalRequestSort.SERVICE, SortOrder.ASC, ["가", "나"]),
        (InternalRequestSort.SERVICE, SortOrder.DESC, ["나", "가"]),
    ],
)
async def test_프로젝트와_서비스는_화면에_보이는_이름순으로_정렬한다(
    db_session: AsyncSession,
    factory: Factory,
    sort: InternalRequestSort,
    order: SortOrder,
    expected: list[str],
) -> None:
    for name in ("나", "가"):
        project = await factory.project(name=name)
        service = await factory.service(name=name)
        await internal_call(
            factory,
            project_id=project["project_id"],
            service_id=service["service_id"],
        )

    page = await list_requests(db_session, PERIOD, query(sort=sort, order=order))

    shown = [
        row.project_name if sort == InternalRequestSort.PROJECT else row.service_name
        for row in page.items
    ]
    assert shown == expected


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        (SortOrder.ASC, ["INTERNAL_DEVELOPMENT", "SIMULATION", "SYSTEM_TEST"]),
        (SortOrder.DESC, ["SYSTEM_TEST", "SIMULATION", "INTERNAL_DEVELOPMENT"]),
    ],
)
async def test_출처는_내부_개발_시뮬레이션_시스템_테스트_순으로_정렬한다(
    db_session: AsyncSession,
    factory: Factory,
    order: SortOrder,
    expected: list[str],
) -> None:
    for origin in ("SIMULATION", "SYSTEM_TEST", "INTERNAL_DEVELOPMENT"):
        await internal_call(factory, usage_origin=origin)

    page = await list_requests(
        db_session, PERIOD, query(sort=InternalRequestSort.ORIGIN, order=order)
    )

    assert [row.usage_origin for row in page.items] == expected


# ---------------------------------------------------------------
# 미리보기와 페이지
# ---------------------------------------------------------------
async def test_미리보기는_최근_20건을_고른_뒤_그_안에서_정렬한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    oldest = await internal_call(
        factory, requested_at=IN_OCTOBER - timedelta(days=1), cost_usd=Decimal(999)
    )
    for minute in range(REQUEST_PREVIEW_ROWS):
        await internal_call(
            factory, requested_at=IN_OCTOBER + timedelta(minutes=minute)
        )

    page = await list_requests(
        db_session,
        PERIOD,
        query(preview=True, sort=InternalRequestSort.COST, order=SortOrder.DESC),
    )

    assert len(page.items) == REQUEST_PREVIEW_ROWS
    assert oldest["request_id"] not in {row.request_id for row in page.items}
    assert page.total == REQUEST_PREVIEW_ROWS + 1


async def test_페이지로_나누고_total은_전체_호출_수이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    for minute in range(5):
        await internal_call(
            factory, requested_at=IN_OCTOBER + timedelta(minutes=minute)
        )

    first = await list_requests(db_session, PERIOD, query(page=1, page_size=2))
    last = await list_requests(db_session, PERIOD, query(page=3, page_size=2))
    beyond = await list_requests(db_session, PERIOD, query(page=4, page_size=2))

    assert (len(first.items), len(last.items), beyond.items) == (2, 1, [])
    assert first.total == last.total == beyond.total == 5
    assert (first.page, first.page_size) == (1, 2)


# ---------------------------------------------------------------
# 요약과의 일치
# ---------------------------------------------------------------
async def test_같은_조건의_목록_비용_합계가_요약의_확정_비용과_같다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await internal_call(factory, cost_usd=Decimal("1.5"))
    await internal_call(factory, usage_origin="SIMULATION", cost_usd=Decimal("2.25"))
    await internal_call(factory, **UNKNOWN_COST)
    await internal_call(factory, usage_origin="CUSTOMER_SERVICE", cost_usd=Decimal(100))

    page = await list_requests(db_session, PERIOD, query(page_size=100))
    summary = await summarize(db_session, PERIOD)

    confirmed = sum(
        (
            row.cost_usd
            for row in page.items
            if row.cost_status == CostStatus.CONFIRMED and row.cost_usd is not None
        ),
        Decimal(0),
    )
    assert confirmed == summary.api_confirmed_usd == Decimal("3.75")
    unknown = sum(row.cost_status == CostStatus.UNKNOWN for row in page.items)
    assert unknown == summary.unknown_cost_count


# ---------------------------------------------------------------
# 선택 목록
# ---------------------------------------------------------------
async def test_선택_목록은_사용_중인_프로젝트와_내부_호출에_쓰인_서비스_모델만_준다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.project(name="나")
    await factory.project(name="가")
    await factory.project(name="중단됨", is_active=False)
    used_service = await factory.service(name="내부 서비스")
    await factory.service(name="안 쓰는 서비스")
    customer_service = await factory.service(name="고객 전용 서비스")
    used_model = await factory.model(display_name="내부 모델")
    await factory.model(display_name="안 쓴 모델")
    customer_model = await factory.model(display_name="고객 전용 모델")
    await internal_call(
        factory, service_id=used_service["service_id"], model_id=used_model["model_id"]
    )
    await internal_call(
        factory,
        usage_origin="CUSTOMER_SERVICE",
        service_id=customer_service["service_id"],
        model_id=customer_model["model_id"],
    )

    options = await list_options(db_session)

    project_names = [option.name for option in options.projects]
    assert project_names.index("가") < project_names.index("나")
    assert "중단됨" not in project_names
    assert [option.name for option in options.services] == ["내부 서비스"]
    assert [option.name for option in options.models] == ["내부 모델"]

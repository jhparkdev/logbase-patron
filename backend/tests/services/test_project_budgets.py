from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.models import SortOrder
from app.schemas.project_budget import (
    ProjectBudgetRow,
    ProjectRowSort,
    ProjectRowsQuery,
)
from app.services.budget_policy import BudgetStatus
from app.services.project_budgets import (
    build_row,
    list_project_budgets,
    project_budget_rows,
    sort_rows,
)
from tests.db_helpers import Factory
from tests.internal_budget_helpers import UNKNOWN_COST, internal_call

OCT = date(2026, 10, 1)
NORMAL = BudgetStatus.NORMAL
WARNING = BudgetStatus.WARNING
OVER = BudgetStatus.OVER
UNSET = BudgetStatus.UNSET


async def test_budget_status_filter_is_applied_before_total_and_pagination(
    db_session: AsyncSession, factory: Factory
) -> None:
    for amount in ("1", "101", "20"):
        project = await factory.project()
        await factory.budget(
            project_id=project["project_id"], monthly_amount_usd=Decimal(100)
        )
        await internal_call(
            factory, project_id=project["project_id"], cost_usd=Decimal(amount)
        )
    page = await list_project_budgets(
        db_session, ProjectRowsQuery(month=OCT, budget_status="OVER", page_size=1)
    )
    assert page.total == 1
    assert len(page.items) == 1
    assert page.items[0].status == OVER


def row(
    project_id: int,
    name: str,
    budget: str | None,
    used: str,
    pct: str | None,
    status: BudgetStatus,
) -> ProjectBudgetRow:
    return ProjectBudgetRow(
        project_id=project_id,
        project_name=name,
        monthly_amount_usd=None if budget is None else Decimal(budget),
        used_usd=Decimal(used),
        usage_pct=None if pct is None else Decimal(pct),
        status=status,
        unknown_cost_count=0,
    )


ROWS = [
    row(1, "beta", "100", "50", "50.00", NORMAL),
    row(2, "alpha", "200", "180", "90.00", WARNING),
    row(3, "gamma", None, "10", None, UNSET),
    row(4, "delta", "50", "60", "120.00", OVER),
]


def ids(rows: list[ProjectBudgetRow]) -> list[int]:
    return [item.project_id for item in rows]


# ---------------------------------------------------------------
# 한 행 계산 (DB 없이)
# ---------------------------------------------------------------
def test_사용액은_API_확정_추정_귀속_구독료의_합이다() -> None:
    result = build_row(1, "p", Decimal(100), Decimal(10), Decimal(20), Decimal(30), 2)

    assert result.used_usd == Decimal(60)
    assert result.usage_pct == Decimal("60.00")
    assert result.status == NORMAL
    assert result.unknown_cost_count == 2


def test_예산이_없으면_사용률은_null이고_상태는_미설정이다() -> None:
    result = build_row(1, "p", None, Decimal(10), Decimal(0), Decimal(0), 0)

    assert result.monthly_amount_usd is None
    assert result.usage_pct is None
    assert result.status == UNSET
    assert result.used_usd == Decimal(10)


@pytest.mark.parametrize(
    ("used", "expected"),
    [
        (Decimal("79.99"), NORMAL),
        (Decimal(80), WARNING),
        (Decimal("99.99"), WARNING),
        (Decimal(100), OVER),
    ],
    ids=["80% 바로 전", "정확히 80%", "100% 바로 전", "정확히 100%"],
)
def test_구독료를_더한_사용액으로_상태를_판단한다(
    used: Decimal, expected: BudgetStatus
) -> None:
    result = build_row(1, "p", Decimal(100), Decimal(0), Decimal(0), used, 0)

    assert result.status == expected


# ---------------------------------------------------------------
# 정렬 (DB 없이)
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("sort", "descending", "expected"),
    [
        (ProjectRowSort.PROJECT, False, [2, 1, 4, 3]),
        (ProjectRowSort.PROJECT, True, [3, 4, 1, 2]),
        (ProjectRowSort.BUDGET, False, [4, 1, 2, 3]),
        (ProjectRowSort.BUDGET, True, [2, 1, 4, 3]),
        (ProjectRowSort.USED, False, [3, 1, 4, 2]),
        (ProjectRowSort.USED, True, [2, 4, 1, 3]),
        (ProjectRowSort.USAGE, False, [1, 2, 4, 3]),
        (ProjectRowSort.USAGE, True, [4, 2, 1, 3]),
        (ProjectRowSort.STATUS, False, [1, 2, 4, 3]),
        (ProjectRowSort.STATUS, True, [4, 2, 1, 3]),
    ],
)
def test_정렬하고_값이_없는_행은_방향과_상관없이_맨_뒤에_둔다(
    sort: ProjectRowSort, descending: bool, expected: list[int]
) -> None:
    assert ids(sort_rows(ROWS, sort, descending)) == expected


def test_같은_값이면_프로젝트_이름순이다() -> None:
    rows = [
        row(1, "beta", "100", "10", "10.00", NORMAL),
        row(2, "alpha", "100", "10", "10.00", NORMAL),
    ]

    assert ids(sort_rows(rows, ProjectRowSort.BUDGET, True)) == [2, 1]
    assert ids(sort_rows(rows, ProjectRowSort.BUDGET, False)) == [2, 1]


@pytest.mark.parametrize("sort", [ProjectRowSort.BUDGET, ProjectRowSort.USAGE])
@pytest.mark.parametrize("descending", [False, True])
def test_예산이_없는_행끼리는_방향과_상관없이_사용액이_높은_순이다(
    sort: ProjectRowSort, descending: bool
) -> None:
    rows = [
        row(1, "a", None, "10", None, UNSET),
        row(2, "b", None, "30", None, UNSET),
        row(3, "c", None, "20", None, UNSET),
        row(4, "d", "100", "5", "5.00", NORMAL),
    ]

    assert ids(sort_rows(rows, sort, descending)) == [4, 2, 3, 1]


def test_예산이_없고_사용액도_같으면_프로젝트_이름순이다() -> None:
    rows = [
        row(1, "beta", None, "10", None, UNSET),
        row(2, "alpha", None, "10", None, UNSET),
    ]

    assert ids(sort_rows(rows, ProjectRowSort.USAGE, True)) == [2, 1]


def test_기본_정렬은_사용률_내림차순이다() -> None:
    query = ProjectRowsQuery(month=OCT)

    assert (query.sort, query.order) == (ProjectRowSort.USAGE, SortOrder.DESC)


# ---------------------------------------------------------------
# DB에서 읽기
# ---------------------------------------------------------------
async def test_사용_중인_프로젝트만_나오고_예산이_없으면_미설정이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    active = await factory.project(name="사용 중")
    await factory.project(name="중단됨", is_active=False)

    rows = await project_budget_rows(db_session, OCT)

    assert [item.project_id for item in rows] == [active["project_id"]]
    assert rows[0].status == UNSET
    assert rows[0].used_usd == 0


@pytest.mark.parametrize(
    ("from_month", "to_month", "applies"),
    [
        (date(2026, 10, 1), None, True),
        (date(2026, 9, 1), None, True),
        (date(2026, 11, 1), None, False),
        (date(2026, 8, 1), date(2026, 9, 1), False),
        (date(2026, 8, 1), date(2026, 10, 1), True),
        (date(2026, 10, 1), date(2026, 10, 1), True),
    ],
    ids=[
        "시작 월",
        "시작 월 이전부터",
        "시작 월이 다음 달",
        "종료 월이 전달",
        "종료 월이 그 달",
        "한 달짜리",
    ],
)
async def test_예산은_적용_기간_안의_달에만_적용된다(
    db_session: AsyncSession,
    factory: Factory,
    from_month: date,
    to_month: date | None,
    applies: bool,
) -> None:
    project = await factory.project()
    await factory.budget(
        project_id=project["project_id"],
        monthly_amount_usd=Decimal(100),
        effective_from_month=from_month,
        effective_to_month=to_month,
    )

    rows = await project_budget_rows(db_session, OCT)

    result = next(item for item in rows if item.project_id == project["project_id"])
    assert (result.monthly_amount_usd == Decimal(100)) is applies


async def test_사용액은_그_달의_API_비용과_귀속_구독료를_더한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project(name="프로젝트 A")
    other = await factory.project(name="프로젝트 B")
    project_id = project["project_id"]
    price = await factory.model_price()
    await factory.budget(project_id=project_id, monthly_amount_usd=Decimal(100))
    await internal_call(factory, project_id=project_id, cost_usd=Decimal(10))
    await internal_call(
        factory,
        project_id=project_id,
        cost_status="ESTIMATED",
        cost_usd=Decimal(20),
        cost_source="PRICE_ESTIMATE",
        price_id=price["price_id"],
    )
    await internal_call(factory, project_id=project_id, **UNKNOWN_COST)
    await factory.subscription_cost(
        applied_month=OCT, amount=Decimal(30), project_id=project_id
    )
    # 아래는 이 프로젝트의 10월 사용액에 들어가면 안 되는 것들이다.
    await factory.subscription_cost(applied_month=OCT, amount=Decimal(1000))
    await factory.subscription_cost(
        applied_month=date(2026, 9, 1), amount=Decimal(1000), project_id=project_id
    )
    await internal_call(factory, project_id=other["project_id"], cost_usd=Decimal(500))
    await internal_call(
        factory,
        project_id=project_id,
        requested_at=datetime(2026, 9, 10, 3, 0, tzinfo=UTC),
        cost_usd=Decimal(1000),
    )

    rows = await project_budget_rows(db_session, OCT)

    by_id = {item.project_id: item for item in rows}
    result = by_id[project_id]
    assert result.monthly_amount_usd == Decimal(100)
    assert result.used_usd == Decimal(60)
    assert result.usage_pct == Decimal("60.00")
    assert result.status == NORMAL
    assert result.unknown_cost_count == 1
    assert by_id[other["project_id"]].used_usd == Decimal(500)
    assert by_id[other["project_id"]].status == UNSET


async def test_AI_도우미_호출은_프로젝트_사용액에_넣는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    await internal_call(
        factory,
        project_id=project["project_id"],
        usage_origin="ASSISTANT",
        cost_usd=Decimal(7),
    )

    rows = await project_budget_rows(db_session, OCT)

    result = next(item for item in rows if item.project_id == project["project_id"])
    assert result.used_usd == Decimal(7)


async def test_고객_사용은_프로젝트_사용액에_넣지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project()
    await internal_call(factory, usage_origin="CUSTOMER_SERVICE", cost_usd=Decimal(100))

    rows = await project_budget_rows(db_session, OCT)

    result = next(item for item in rows if item.project_id == project["project_id"])
    assert result.used_usd == 0


@pytest.mark.parametrize(
    ("requested_at", "expected"),
    [
        (datetime(2026, 9, 30, 14, 59, 59, 999999, tzinfo=UTC), 0),
        (datetime(2026, 9, 30, 15, 0, tzinfo=UTC), 1),
        (datetime(2026, 10, 31, 14, 59, 59, 999999, tzinfo=UTC), 1),
        (datetime(2026, 10, 31, 15, 0, tzinfo=UTC), 0),
    ],
    ids=["시작 직전", "시작 정각", "말일 마지막", "다음 달 0시"],
)
async def test_월_경계는_KST_기준이다(
    db_session: AsyncSession, factory: Factory, requested_at: datetime, expected: int
) -> None:
    project = await factory.project()
    await internal_call(
        factory, project_id=project["project_id"], requested_at=requested_at
    )

    rows = await project_budget_rows(db_session, OCT)

    assert rows[0].used_usd == Decimal(expected)


# ---------------------------------------------------------------
# 미리보기와 페이지
# ---------------------------------------------------------------
async def seven_projects(factory: Factory) -> None:
    for number in range(1, 8):
        project = await factory.project(name=f"project {number}")
        await internal_call(
            factory, project_id=project["project_id"], cost_usd=Decimal(number)
        )


async def usage_project(
    factory: Factory, name: str, *, cost: str, budget: str | None = None
) -> int:
    project = await factory.project(name=name)
    if budget is not None:
        await factory.budget(
            project_id=project["project_id"], monthly_amount_usd=Decimal(budget)
        )
    await internal_call(
        factory, project_id=project["project_id"], cost_usd=Decimal(cost)
    )
    return project["project_id"]


async def test_기본은_사용률이_높은_순서이고_예산이_없는_프로젝트는_맨_뒤다(
    db_session: AsyncSession, factory: Factory
) -> None:
    # 사용액은 정상이 더 크지만 예산을 넘긴 프로젝트가 위에 와야 한다.
    await usage_project(factory, "정상", cost="1000", budget="5000")
    await usage_project(factory, "미설정", cost="700")
    await usage_project(factory, "초과", cost="150", budget="100")

    page = await list_project_budgets(db_session, ProjectRowsQuery(month=OCT))

    assert [item.project_name for item in page.items] == ["초과", "정상", "미설정"]


async def test_예산이_없으면_사용액이_큰_순서로_페이지를_나눈다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await seven_projects(factory)

    first = await list_project_budgets(
        db_session, ProjectRowsQuery(month=OCT, page=1, page_size=3)
    )
    second = await list_project_budgets(
        db_session, ProjectRowsQuery(month=OCT, page=2, page_size=3)
    )

    assert [item.project_name for item in first.items] == [
        "project 7",
        "project 6",
        "project 5",
    ]
    assert [item.project_name for item in second.items] == [
        "project 4",
        "project 3",
        "project 2",
    ]
    assert first.total == second.total == 7


async def test_마지막_페이지를_넘으면_빈_목록이고_total은_그대로이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await seven_projects(factory)

    page = await list_project_budgets(
        db_session, ProjectRowsQuery(month=OCT, page=5, page_size=3)
    )

    assert page.items == []
    assert page.total == 7


async def test_미리보기는_사용률_상위_5개를_고른_뒤_그_안에서_정렬한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    for number in range(1, 7):
        await usage_project(factory, f"p{number}", cost=str(number * 10), budget="100")
    # 사용액은 가장 크지만 사용률은 가장 낮다. 미리보기에 들어오면 안 된다.
    await usage_project(factory, "큰 예산", cost="500", budget="100000")
    query = ProjectRowsQuery(
        month=OCT, preview=True, sort=ProjectRowSort.PROJECT, order=SortOrder.ASC
    )

    page = await list_project_budgets(db_session, query)

    assert [item.project_name for item in page.items] == [
        "p2",
        "p3",
        "p4",
        "p5",
        "p6",
    ]
    assert page.total == 7


async def test_예산이_있는_프로젝트가_5개보다_적으면_사용액이_큰_미설정_프로젝트로_채운다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await usage_project(factory, "b1", cost="10", budget="100")
    await usage_project(factory, "b2", cost="20", budget="100")
    for number in range(1, 5):
        await usage_project(factory, f"u{number}", cost=str(number))
    query = ProjectRowsQuery(
        month=OCT, preview=True, sort=ProjectRowSort.PROJECT, order=SortOrder.ASC
    )

    page = await list_project_budgets(db_session, query)

    assert [item.project_name for item in page.items] == [
        "b1",
        "b2",
        "u2",
        "u3",
        "u4",
    ]


async def test_예산이_없으면_사용액_상위_5개를_고른_뒤_그_안에서_정렬한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await seven_projects(factory)
    query = ProjectRowsQuery(
        month=OCT, preview=True, sort=ProjectRowSort.PROJECT, order=SortOrder.ASC
    )

    page = await list_project_budgets(db_session, query)

    assert [item.project_name for item in page.items] == [
        "project 3",
        "project 4",
        "project 5",
        "project 6",
        "project 7",
    ]
    assert page.total == 7


# ---------------------------------------------------------------
# 프로젝트·모델 조건
# ---------------------------------------------------------------
async def test_프로젝트를_고르면_그_프로젝트_한_행만_나온다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await usage_project(factory, "다른", cost="5", budget="100")
    target = await usage_project(factory, "대상", cost="10", budget="100")

    page = await list_project_budgets(
        db_session, ProjectRowsQuery(month=OCT, project_id=target)
    )

    assert [item.project_id for item in page.items] == [target]
    assert page.total == 1


async def test_없는_프로젝트를_고르면_빈_목록이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await usage_project(factory, "있는", cost="5")

    page = await list_project_budgets(
        db_session, ProjectRowsQuery(month=OCT, project_id=987654)
    )

    assert (page.items, page.total) == ([], 0)


async def test_모델을_고르면_그_모델의_호출만_사용액이고_구독료는_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project(name="프로젝트")
    project_id = project["project_id"]
    model = await factory.model()
    other = await factory.model()
    await factory.budget(project_id=project_id, monthly_amount_usd=Decimal(100))
    await internal_call(
        factory, project_id=project_id, model_id=model["model_id"], cost_usd=Decimal(10)
    )
    await internal_call(
        factory, project_id=project_id, model_id=other["model_id"], cost_usd=Decimal(30)
    )
    await internal_call(
        factory, project_id=project_id, model_id=other["model_id"], **UNKNOWN_COST
    )
    await factory.subscription_cost(
        applied_month=OCT, amount=Decimal(5), project_id=project_id
    )

    unfiltered = await project_budget_rows(db_session, OCT)
    filtered = await project_budget_rows(db_session, OCT, model_id=model["model_id"])

    assert unfiltered[0].used_usd == Decimal(45)
    assert filtered[0].used_usd == Decimal(10)
    assert filtered[0].unknown_cost_count == 0
    assert unfiltered[0].unknown_cost_count == 1


async def test_프로젝트와_모델을_함께_고르면_둘_다_맞는_호출만_사용액이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    mine = await factory.project(name="내 프로젝트")
    other = await factory.project(name="다른 프로젝트")
    model = await factory.model()
    for project in (mine, other):
        await internal_call(
            factory,
            project_id=project["project_id"],
            model_id=model["model_id"],
            cost_usd=Decimal(7),
        )

    rows = await project_budget_rows(
        db_session, OCT, project_id=mine["project_id"], model_id=model["model_id"]
    )

    pairs = [(row.project_id, row.used_usd) for row in rows]
    assert pairs == [(mine["project_id"], Decimal(7))]

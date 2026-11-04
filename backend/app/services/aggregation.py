"""P-01 고객 사용량 집계. 호출 이력(ai_requests)의 CUSTOMER_SERVICE 행만 읽는다.

요약·추이·표는 같은 조건식을 써서 같은 조건의 합계가 서로 일치한다.
미확인 비용은 금액 합계에 넣지 않고 건수로만 센다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import (
    Cast,
    ColumnElement,
    Date,
    Select,
    case,
    collate,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    Budget,
    BudgetScopeType,
    CostStatus,
    Customer,
    ModelRegistry,
    RequestStatus,
    Service,
    ServiceType,
    Task,
    UsageOrigin,
)
from app.schemas.models import SortOrder
from app.schemas.usage import (
    BudgetUsage,
    CustomerRequestPage,
    CustomerRequestRow,
    CustomerRowSort,
    CustomerRowsQuery,
    CustomerServiceUsage,
    CustomerUsageDetail,
    CustomerUsagePage,
    CustomerUsageRow,
    RequestRowSort,
    RequestRowsQuery,
    UsageOption,
    UsageOptions,
    UsageSummary,
    UsageTrend,
    UsageTrendPoint,
)
from app.services.budget_policy import (
    WARNING_PCT,
    BudgetStatus,
    evaluate_budget,
    share_of_budget,
)
from app.services.simulation_period import DateRange, utc_bounds

# 요약 화면의 미리보기 건수
CUSTOMER_PREVIEW_ROWS = 5
REQUEST_PREVIEW_ROWS = 20
KST_ZONE = "Asia/Seoul"
HUNDRED = Decimal(100)
CHANGE_PRECISION = Decimal("0.01")
ZERO = Decimal(0)
# 작업 유형 코드의 화면 표시 이름. 목록에 없는 코드는 내부 코드가 화면에 나가지 않게 기타로 보여 준다
TASK_TYPE_LABELS = {
    "PRODUCT_DESCRIPTION": "상품 설명 생성",
    "CATALOG_SUMMARY": "카탈로그 요약",
    "IMAGE_ANALYSIS": "이미지 분석",
}
OTHER_TASK_TYPE_LABEL = "기타"
# DB 기본 정렬 규칙(en_US.utf8)은 띄어쓰기가 든 한글을 가나다순으로 정렬하지 않는다.
# 한글 음절은 코드값 순서가 가나다순이고 고객 표의 메모리 정렬과도 같아 C 규칙을 쓴다
CODE_POINT_COLLATION = "C"
# 상태 정렬 순서는 심각한 정도다. 미설정은 값이 없어 어느 방향이든 맨 뒤에 둔다
STATUS_SEVERITY = {
    BudgetStatus.NORMAL: 0,
    BudgetStatus.WARNING: 1,
    BudgetStatus.OVER: 2,
}


@dataclass(frozen=True)
class UsageFilter:
    period: DateRange
    customer_id: int | None = None
    service_id: int | None = None
    model_id: int | None = None


def _by_name(column: Any) -> ColumnElement[str]:
    return collate(column, CODE_POINT_COLLATION)


def change_pct(current: Decimal, previous: Decimal) -> Decimal | None:
    """이전 값 대비 증감률(%). 이전 값이 0이면 비율을 정의할 수 없어 None이다."""
    if previous == 0:
        return None
    return ((current - previous) * HUNDRED / previous).quantize(
        CHANGE_PRECISION, ROUND_HALF_UP
    )


def previous_period(period: DateRange) -> DateRange:
    """바로 앞의 같은 길이 기간."""
    end = period.start - timedelta(days=1)
    return DateRange(end - (period.end - period.start), end)


def budget_month_of(period: DateRange) -> date:
    """예산을 비교하는 달: 조회 기간 종료일이 속한 KST 달의 1일."""
    return period.end.replace(day=1)


def _month_period(month: date) -> DateRange:
    next_month = (month.replace(day=1) + timedelta(days=32)).replace(day=1)
    return DateRange(month, next_month - timedelta(days=1))


def _conditions(usage_filter: UsageFilter) -> list[ColumnElement[bool]]:
    start, end = utc_bounds(usage_filter.period)
    conditions = [
        AIRequest.usage_origin == UsageOrigin.CUSTOMER_SERVICE.value,
        AIRequest.requested_at >= start,
        AIRequest.requested_at < end,
    ]
    if usage_filter.customer_id is not None:
        conditions.append(AIRequest.customer_id == usage_filter.customer_id)
    if usage_filter.service_id is not None:
        conditions.append(AIRequest.service_id == usage_filter.service_id)
    if usage_filter.model_id is not None:
        conditions.append(AIRequest.model_id == usage_filter.model_id)
    return conditions


def _cost_total(cost_status: CostStatus) -> ColumnElement[Decimal]:
    return func.coalesce(
        func.sum(AIRequest.cost_usd).filter(AIRequest.cost_status == cost_status.value),
        ZERO,
    )


def _status_count(status: RequestStatus) -> ColumnElement[int]:
    return func.count().filter(AIRequest.status == status.value)


def _measures() -> list[Any]:
    """표와 추이가 함께 쓰는 집계 값. 결과 행의 이름은 응답 필드와 같다."""
    return [
        func.count(AIRequest.task_id.distinct()).label("task_count"),
        func.count().label("call_count"),
        _cost_total(CostStatus.CONFIRMED).label("confirmed_cost_usd"),
        _cost_total(CostStatus.ESTIMATED).label("estimated_cost_usd"),
        func.count()
        .filter(AIRequest.cost_status == CostStatus.UNKNOWN.value)
        .label("unknown_cost_count"),
    ]


async def _period_totals(session: AsyncSession, usage_filter: UsageFilter) -> Any:
    statement = select(
        *_measures(),
        _status_count(RequestStatus.SUCCESS).label("success_count"),
        _status_count(RequestStatus.FAILED).label("failed_count"),
        _status_count(RequestStatus.TIMEOUT).label("timeout_count"),
        func.coalesce(func.sum(AIRequest.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(AIRequest.output_tokens), 0).label("output_tokens"),
    ).where(*_conditions(usage_filter))
    return (await session.execute(statement)).one()


async def summarize(session: AsyncSession, usage_filter: UsageFilter) -> UsageSummary:
    comparison = previous_period(usage_filter.period)
    current = await _period_totals(session, usage_filter)
    previous = await _period_totals(
        session,
        UsageFilter(
            comparison,
            usage_filter.customer_id,
            usage_filter.service_id,
            usage_filter.model_id,
        ),
    )
    return UsageSummary(
        comparison_start_date=comparison.start,
        comparison_end_date=comparison.end,
        task_count=current.task_count,
        call_count=current.call_count,
        success_count=current.success_count,
        failed_count=current.failed_count,
        timeout_count=current.timeout_count,
        input_tokens=current.input_tokens,
        output_tokens=current.output_tokens,
        confirmed_cost_usd=current.confirmed_cost_usd,
        estimated_cost_usd=current.estimated_cost_usd,
        unknown_cost_count=current.unknown_cost_count,
        task_change_pct=change_pct(
            Decimal(current.task_count), Decimal(previous.task_count)
        ),
        call_change_pct=change_pct(
            Decimal(current.call_count), Decimal(previous.call_count)
        ),
        confirmed_cost_change_pct=change_pct(
            current.confirmed_cost_usd, previous.confirmed_cost_usd
        ),
        estimated_cost_change_pct=change_pct(
            current.estimated_cost_usd, previous.estimated_cost_usd
        ),
    )


async def daily_trend(session: AsyncSession, usage_filter: UsageFilter) -> UsageTrend:
    kst_day: Cast[date] = func.timezone(KST_ZONE, AIRequest.requested_at).cast(Date)
    rows = await session.execute(
        select(kst_day.label("day"), *_measures())
        .where(*_conditions(usage_filter))
        .group_by(kst_day)
    )
    by_day = {row.day: row for row in rows}
    period = usage_filter.period
    days = (period.start + timedelta(days=n) for n in _day_offsets(period))
    return UsageTrend(items=[_trend_point(day, by_day.get(day)) for day in days])


def _day_offsets(period: DateRange) -> range:
    return range((period.end - period.start).days + 1)


def _trend_point(day: date, row: Any | None) -> UsageTrendPoint:
    if row is None:
        return UsageTrendPoint(
            date=day,
            task_count=0,
            call_count=0,
            confirmed_cost_usd=ZERO,
            estimated_cost_usd=ZERO,
            unknown_cost_count=0,
        )
    return UsageTrendPoint(
        date=day,
        task_count=row.task_count,
        call_count=row.call_count,
        confirmed_cost_usd=row.confirmed_cost_usd,
        estimated_cost_usd=row.estimated_cost_usd,
        unknown_cost_count=row.unknown_cost_count,
    )


async def list_options(session: AsyncSession) -> UsageOptions:
    customers = await session.execute(
        select(Customer.customer_id, Customer.name).order_by(_by_name(Customer.name))
    )
    services = await session.execute(
        select(Service.service_id, Service.name)
        .where(Service.service_type == ServiceType.CUSTOMER_FACING.value)
        .order_by(_by_name(Service.name))
    )
    used_by_customers = select(AIRequest.model_id).where(
        AIRequest.usage_origin == UsageOrigin.CUSTOMER_SERVICE.value
    )
    models = await session.execute(
        select(ModelRegistry.model_id, ModelRegistry.display_name)
        .where(ModelRegistry.model_id.in_(used_by_customers))
        .order_by(_by_name(ModelRegistry.display_name))
    )
    return UsageOptions(
        customers=_options(customers),
        services=_options(services),
        models=_options(models),
    )


def _options(rows: Any) -> list[UsageOption]:
    return [UsageOption(id=row[0], name=row[1]) for row in rows]


# 예산


async def _budget_usages(
    session: AsyncSession, customer_ids: set[int | None], month: date
) -> dict[int | None, BudgetUsage]:
    """고객별 그 달 예산 현황. 사용액은 조회 필터와 관계없이 고객 전체 서비스 합계다."""
    start, end = utc_bounds(_month_period(month))
    usage_rows = await session.execute(
        select(AIRequest.customer_id, *_measures())
        .where(
            AIRequest.usage_origin == UsageOrigin.CUSTOMER_SERVICE.value,
            AIRequest.requested_at >= start,
            AIRequest.requested_at < end,
        )
        .group_by(AIRequest.customer_id)
    )
    usage = {row.customer_id: row for row in usage_rows}
    budget_rows = await session.scalars(
        select(Budget).where(
            Budget.scope_type == BudgetScopeType.CUSTOMER.value,
            Budget.effective_from_month <= month,
            or_(
                Budget.effective_to_month.is_(None),
                Budget.effective_to_month >= month,
            ),
        )
    )
    budgets = {budget.customer_id: budget for budget in budget_rows}
    return {
        customer_id: _budget_usage(
            month, budgets.get(customer_id), usage.get(customer_id)
        )
        for customer_id in customer_ids
    }


def _budget_usage(month: date, budget: Budget | None, usage: Any | None) -> BudgetUsage:
    confirmed = usage.confirmed_cost_usd if usage is not None else ZERO
    estimated = usage.estimated_cost_usd if usage is not None else ZERO
    amount = budget.monthly_amount_usd if budget is not None else None
    evaluation = evaluate_budget(amount, confirmed, estimated)
    return BudgetUsage(
        month=month,
        monthly_amount_usd=amount,
        effective_from_month=budget.effective_from_month if budget else None,
        used_usd=evaluation.used_usd,
        usage_pct=evaluation.usage_pct,
        confirmed_usage_pct=evaluation.confirmed_usage_pct,
        remaining_usd=evaluation.remaining_usd,
        unknown_cost_count=usage.unknown_cost_count if usage is not None else 0,
        status=evaluation.status,
        warning_threshold_pct=WARNING_PCT,
    )


# 고객 표


async def list_customer_rows(
    session: AsyncSession, usage_filter: UsageFilter, query: CustomerRowsQuery
) -> CustomerUsagePage:
    """행 수가 고객 × 서비스로 작아 메모리에서 정렬한다.

    예산 상태 정렬이 판단 함수(budget_policy)의 결과를 그대로 쓰게 하기 위해서다.
    SQL로 정렬하면 같은 기준을 SQL에 또 적어야 한다.
    """
    rows = await session.execute(
        select(
            AIRequest.customer_id,
            Customer.name.label("customer_name"),
            AIRequest.service_id,
            Service.name.label("service_name"),
            *_measures(),
        )
        .join(Service, Service.service_id == AIRequest.service_id)
        .outerjoin(Customer, Customer.customer_id == AIRequest.customer_id)
        .where(*_conditions(usage_filter))
        .group_by(
            AIRequest.customer_id, Customer.name, AIRequest.service_id, Service.name
        )
    )
    groups = list(rows)
    budgets = await _budget_usages(
        session,
        {group.customer_id for group in groups},
        budget_month_of(usage_filter.period),
    )
    items = [
        CustomerUsageRow(
            customer_id=group.customer_id,
            customer_name=group.customer_name,
            service_id=group.service_id,
            service_name=group.service_name,
            task_count=group.task_count,
            call_count=group.call_count,
            confirmed_cost_usd=group.confirmed_cost_usd,
            estimated_cost_usd=group.estimated_cost_usd,
            unknown_cost_count=group.unknown_cost_count,
            budget=budgets[group.customer_id],
        )
        for group in groups
    ]
    if query.budget_status is not None:
        items = [item for item in items if item.budget.status == query.budget_status]
    return CustomerUsagePage(
        items=_customer_page(items, query),
        total=len(items),
        page=query.page,
        page_size=query.page_size,
    )


def _customer_page(
    items: list[CustomerUsageRow], query: CustomerRowsQuery
) -> list[CustomerUsageRow]:
    if query.preview:
        top = _sorted_rows(items, _customer_sort_key(CustomerRowSort.CONFIRMED), True)
        chosen = top[:CUSTOMER_PREVIEW_ROWS]
        return _sorted_rows(
            chosen, _customer_sort_key(query.sort), query.order == SortOrder.DESC
        )
    ordered = _sorted_rows(
        items, _customer_sort_key(query.sort), query.order == SortOrder.DESC
    )
    start = (query.page - 1) * query.page_size
    return ordered[start : start + query.page_size]


def _sorted_rows(
    items: list[CustomerUsageRow],
    key: Callable[[CustomerUsageRow], Any],
    descending: bool,
) -> list[CustomerUsageRow]:
    """값이 없는 행(미분류·예산 미설정)은 정렬 방향과 관계없이 맨 뒤에 둔다. 같은 값은 이름순이다."""
    by_name = sorted(items, key=lambda row: (row.customer_name or "", row.service_name))
    present = [row for row in by_name if key(row) is not None]
    missing = [row for row in by_name if key(row) is None]
    return sorted(present, key=key, reverse=descending) + missing


def _customer_sort_key(sort: CustomerRowSort) -> Callable[[CustomerUsageRow], Any]:
    keys: dict[CustomerRowSort, Callable[[CustomerUsageRow], Any]] = {
        CustomerRowSort.CUSTOMER: lambda row: row.customer_name,
        CustomerRowSort.SERVICE: lambda row: row.service_name,
        CustomerRowSort.TASKS: lambda row: row.task_count,
        CustomerRowSort.CALLS: lambda row: row.call_count,
        CustomerRowSort.CONFIRMED: lambda row: row.confirmed_cost_usd,
        CustomerRowSort.ESTIMATED: lambda row: row.estimated_cost_usd,
        CustomerRowSort.BUDGET: lambda row: row.budget.monthly_amount_usd,
        CustomerRowSort.USAGE: lambda row: row.budget.usage_pct,
        CustomerRowSort.STATUS: lambda row: STATUS_SEVERITY.get(row.budget.status),
    }
    return keys[sort]


# 호출 표


async def list_requests(
    session: AsyncSession, usage_filter: UsageFilter, query: RequestRowsQuery
) -> CustomerRequestPage:
    conditions = _conditions(usage_filter)
    total = await session.scalar(
        select(func.count()).select_from(AIRequest).where(*conditions)
    )
    statement = _request_rows().where(*conditions).order_by(*_request_order(query))
    if query.preview:
        # 최근 N건을 먼저 고른다. 정렬해도 "최근 N건"의 뜻이 바뀌지 않게 하기 위해서다
        latest = (
            select(AIRequest.request_id)
            .where(*conditions)
            .order_by(AIRequest.requested_at.desc(), AIRequest.request_id.desc())
            .limit(REQUEST_PREVIEW_ROWS)
        )
        statement = statement.where(AIRequest.request_id.in_(latest))
    else:
        statement = statement.offset((query.page - 1) * query.page_size).limit(
            query.page_size
        )
    rows = await session.execute(statement)
    return CustomerRequestPage(
        items=[CustomerRequestRow.model_validate(dict(row)) for row in rows.mappings()],
        total=total or 0,
        page=query.page,
        page_size=query.page_size,
    )


def _model_column() -> ColumnElement[str]:
    return func.coalesce(AIRequest.actual_model, AIRequest.requested_model)


def _task_type_label_column() -> ColumnElement[str | None]:
    """표시 이름. 정렬도 이 값으로 해서 화면에 보이는 글자 순서와 맞춘다. 작업이 없으면 NULL이다."""
    labels = [
        (Task.task_type == code, label) for code, label in TASK_TYPE_LABELS.items()
    ]
    return case((Task.task_type.is_(None), None), *labels, else_=OTHER_TASK_TYPE_LABEL)


def _tokens_column() -> ColumnElement[int]:
    # 어느 한쪽이 NULL이면 합도 NULL이다. 모르는 토큰을 0으로 더하지 않는다
    return AIRequest.input_tokens + AIRequest.output_tokens


def _request_rows() -> Select[Any]:
    return (
        select(
            AIRequest.request_id,
            AIRequest.requested_at,
            AIRequest.customer_id,
            Customer.name.label("customer_name"),
            AIRequest.service_id,
            Service.name.label("service_name"),
            _model_column().label("model"),
            AIRequest.task_id,
            Task.task_type,
            _task_type_label_column().label("task_type_label"),
            _tokens_column().label("tokens"),
            AIRequest.cost_usd,
            AIRequest.cost_status,
            AIRequest.status,
            AIRequest.error_type,
        )
        .join(Service, Service.service_id == AIRequest.service_id)
        .outerjoin(Customer, Customer.customer_id == AIRequest.customer_id)
        .outerjoin(Task, Task.task_id == AIRequest.task_id)
    )


def _request_order(query: RequestRowsQuery) -> list[Any]:
    """값이 없는 행(미확인 비용 등)은 방향과 관계없이 맨 뒤다. 끝의 두 열로 순서를 고정한다."""
    columns: dict[RequestRowSort, Any] = {
        RequestRowSort.REQUESTED_AT: AIRequest.requested_at,
        RequestRowSort.CUSTOMER: _by_name(Customer.name),
        RequestRowSort.SERVICE: _by_name(Service.name),
        RequestRowSort.MODEL: _model_column(),
        RequestRowSort.TASK_TYPE: _by_name(_task_type_label_column()),
        RequestRowSort.TOKENS: _tokens_column(),
        RequestRowSort.COST: AIRequest.cost_usd,
        RequestRowSort.COST_STATUS: AIRequest.cost_status,
        RequestRowSort.STATUS: AIRequest.status,
    }
    column = columns[query.sort]
    primary = column.desc() if query.order == SortOrder.DESC else column.asc()
    return [
        primary.nulls_last(),
        AIRequest.requested_at.desc(),
        AIRequest.request_id.desc(),
    ]


# 고객 상세


async def customer_detail(
    session: AsyncSession, customer_id: int, month: date
) -> CustomerUsageDetail | None:
    """그 달의 고객 전체 사용량과 서비스별 사용량. 고객이 없으면 None."""
    name = await session.scalar(
        select(Customer.name).where(Customer.customer_id == customer_id)
    )
    if name is None:
        return None
    usage_filter = UsageFilter(_month_period(month), customer_id=customer_id)
    totals = (
        await session.execute(select(*_measures()).where(*_conditions(usage_filter)))
    ).one()
    budgets = await _budget_usages(session, {customer_id}, month)
    budget = budgets[customer_id]
    service_rows = await session.execute(
        select(
            AIRequest.service_id,
            Service.name.label("service_name"),
            *_measures(),
        )
        .join(Service, Service.service_id == AIRequest.service_id)
        .where(*_conditions(usage_filter))
        .group_by(AIRequest.service_id, Service.name)
        .order_by(_by_name(Service.name))
    )
    return CustomerUsageDetail(
        customer_id=customer_id,
        customer_name=name,
        month=month,
        task_count=totals.task_count,
        call_count=totals.call_count,
        confirmed_cost_usd=totals.confirmed_cost_usd,
        estimated_cost_usd=totals.estimated_cost_usd,
        unknown_cost_count=totals.unknown_cost_count,
        budget=budget,
        services=[
            _service_usage(row, budget.monthly_amount_usd) for row in service_rows
        ],
    )


def _service_usage(row: Any, monthly_amount: Decimal | None) -> CustomerServiceUsage:
    total = row.confirmed_cost_usd + row.estimated_cost_usd
    return CustomerServiceUsage(
        service_id=row.service_id,
        service_name=row.service_name,
        task_count=row.task_count,
        call_count=row.call_count,
        confirmed_cost_usd=row.confirmed_cost_usd,
        estimated_cost_usd=row.estimated_cost_usd,
        total_cost_usd=total,
        unknown_cost_count=row.unknown_cost_count,
        budget_share_pct=share_of_budget(total, monthly_amount),
    )

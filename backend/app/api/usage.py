"""고객 AI 사용 현황(P-01) 경로. 입력 검증과 응답 변환만 하고, 집계는 services/aggregation이 한다.

로그인 검사는 팀 결정으로 뒤로 미뤘다(main.py). 복구할 때 이 라우터도 함께 대상이 된다.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import DevUserDep, NowDep
from app.api.errors import ApiError
from app.db import SessionDep
from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.models import MAX_MODEL_ID
from app.schemas.usage import (
    CustomerBudgetRead,
    CustomerBudgetSave,
    CustomerMonthQuery,
    CustomerRequestPage,
    CustomerRowsQuery,
    CustomerUsageDetail,
    CustomerUsagePage,
    RequestRowsQuery,
    UsageFilterQuery,
    UsageOptions,
    UsageSummary,
    UsageTrend,
)
from app.services import aggregation, customer_budgets
from app.services.aggregation import UsageFilter
from app.services.customer_budgets import (
    BudgetPeriodConflictError,
    CustomerNotFoundError,
)
from app.services.simulation_period import (
    InvalidPeriodError,
    InvalidPeriodReason,
    kst_today,
    resolve_period,
)

CUSTOMER_NOT_FOUND_MESSAGE = "고객을 찾을 수 없어요."
BUDGET_CONFLICT_MESSAGE = (
    "이미 적용 중이거나 예정된 예산과 기간이 겹쳐요. 적용 시작 월을 확인해 주세요."
)
PERIOD_MESSAGES = {
    InvalidPeriodReason.INCOMPLETE: "시작일과 종료일을 모두 선택해 주세요.",
    InvalidPeriodReason.START_AFTER_END: "시작일은 종료일보다 늦을 수 없어요.",
    InvalidPeriodReason.TOO_LONG: "기간은 최대 366일까지 조회할 수 있어요. 기간을 줄여 주세요.",
}

QUERY_ERRORS = {status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}}
DETAIL_ERRORS = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
SAVE_ERRORS = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}

CustomerIdPath = Annotated[int, Path(ge=1, le=MAX_MODEL_ID)]

router = APIRouter(prefix="/usage/customers", tags=["customer-usage"])


def _usage_filter(query: UsageFilterQuery, today: date) -> UsageFilter:
    try:
        period = resolve_period(query.start_date, query.end_date, today)
    except InvalidPeriodError as error:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.INVALID_PERIOD,
            PERIOD_MESSAGES[error.reason],
        ) from error
    return UsageFilter(period, query.customer_id, query.service_id, query.model_id)


def _customer_not_found() -> ApiError:
    return ApiError(
        status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, CUSTOMER_NOT_FOUND_MESSAGE
    )


@router.get("/options")
async def read_options(session: SessionDep) -> UsageOptions:
    return await aggregation.list_options(session)


@router.get("/summary", responses=QUERY_ERRORS)
async def read_summary(
    query: Annotated[UsageFilterQuery, Query()], session: SessionDep, now: NowDep
) -> UsageSummary:
    return await aggregation.summarize(session, _usage_filter(query, kst_today(now)))


@router.get("/trend", responses=QUERY_ERRORS)
async def read_trend(
    query: Annotated[UsageFilterQuery, Query()], session: SessionDep, now: NowDep
) -> UsageTrend:
    return await aggregation.daily_trend(session, _usage_filter(query, kst_today(now)))


@router.get("/rows", responses=QUERY_ERRORS)
async def read_customer_rows(
    query: Annotated[CustomerRowsQuery, Query()], session: SessionDep, now: NowDep
) -> CustomerUsagePage:
    usage_filter = _usage_filter(query, kst_today(now))
    return await aggregation.list_customer_rows(session, usage_filter, query)


@router.get("/requests", responses=QUERY_ERRORS)
async def read_requests(
    query: Annotated[RequestRowsQuery, Query()], session: SessionDep, now: NowDep
) -> CustomerRequestPage:
    usage_filter = _usage_filter(query, kst_today(now))
    return await aggregation.list_requests(session, usage_filter, query)


@router.get("/{customer_id}", responses=DETAIL_ERRORS)
async def read_customer_detail(
    customer_id: CustomerIdPath,
    query: Annotated[CustomerMonthQuery, Query()],
    session: SessionDep,
) -> CustomerUsageDetail:
    detail = await aggregation.customer_detail(session, customer_id, query.month)
    if detail is None:
        raise _customer_not_found()
    return detail


@router.put("/{customer_id}/budget", responses=SAVE_ERRORS)
async def save_customer_budget(
    customer_id: CustomerIdPath,
    body: CustomerBudgetSave,
    session: SessionDep,
    user: DevUserDep,
) -> CustomerBudgetRead:
    try:
        budget = await customer_budgets.save_customer_budget(
            session,
            customer_id,
            body.monthly_amount_usd,
            body.effective_from_month,
            user.user_id,
        )
    except CustomerNotFoundError as error:
        raise _customer_not_found() from error
    except BudgetPeriodConflictError as error:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            ErrorCode.BUDGET_PERIOD_CONFLICT,
            BUDGET_CONFLICT_MESSAGE,
        ) from error
    return CustomerBudgetRead(
        budget_id=budget.budget_id,
        customer_id=customer_id,
        monthly_amount_usd=budget.monthly_amount_usd,
        effective_from_month=budget.effective_from_month,
        effective_to_month=budget.effective_to_month,
    )

"""내부 AI 예산 관리(P-02) 경로. 입력 검증과 응답 변환만 하고, 집계는 services/internal_usage가 한다."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.deps import CurrentUserDep, NowDep
from app.api.errors import ApiError
from app.api.usage import (
    BUDGET_CONFLICT_MESSAGE,
    DETAIL_ERRORS,
    PERIOD_MESSAGES,
    QUERY_ERRORS,
    SAVE_ERRORS,
)
from app.db import SessionDep
from app.schemas.common import ErrorCode
from app.schemas.internal_requests import (
    InternalOptions,
    InternalRequestPage,
    InternalRequestsQuery,
)
from app.schemas.internal_usage import (
    InternalFilterQuery,
    InternalSummary,
    InternalTrend,
    InternalUsageQuery,
)
from app.schemas.models import MAX_MODEL_ID
from app.schemas.project_budget import ProjectBudgetPage, ProjectRowsQuery
from app.schemas.project_budget_save import ProjectBudgetRead, ProjectBudgetSave
from app.schemas.project_detail import ProjectMonthQuery, ProjectUsageDetail
from app.services import (
    internal_requests,
    internal_usage,
    project_budget_save,
    project_budgets,
    project_detail,
)
from app.services.project_budget_save import (
    ProjectBudgetConflictError,
    ProjectNotFoundError,
)
from app.services.simulation_period import (
    DateRange,
    InvalidPeriodError,
    kst_today,
    resolve_period,
)

PROJECT_NOT_FOUND_MESSAGE = "프로젝트를 찾을 수 없어요."
ProjectIdPath = Annotated[int, Path(ge=1, le=MAX_MODEL_ID)]

router = APIRouter(prefix="/usage/internal", tags=["internal-budget"])


def _project_not_found() -> ApiError:
    return ApiError(
        status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, PROJECT_NOT_FOUND_MESSAGE
    )


def period_of(query: InternalFilterQuery, today: date) -> DateRange:
    try:
        return resolve_period(query.start_date, query.end_date, today)
    except InvalidPeriodError as error:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.INVALID_PERIOD,
            PERIOD_MESSAGES[error.reason],
        ) from error


@router.get("/summary", responses=QUERY_ERRORS)
async def read_summary(
    query: Annotated[InternalUsageQuery, Query()], session: SessionDep, now: NowDep
) -> InternalSummary:
    period = period_of(query, kst_today(now))
    return await internal_usage.summarize(
        session, period, query.project_id, query.model_id
    )


@router.get("/trend", responses=QUERY_ERRORS)
async def read_trend(
    query: Annotated[InternalUsageQuery, Query()], session: SessionDep, now: NowDep
) -> InternalTrend:
    period = period_of(query, kst_today(now))
    return await internal_usage.daily_trend(
        session, period, query.project_id, query.model_id
    )


@router.get("/requests", responses=QUERY_ERRORS)
async def read_requests(
    query: Annotated[InternalRequestsQuery, Query()], session: SessionDep, now: NowDep
) -> InternalRequestPage:
    period = period_of(query, kst_today(now))
    return await internal_requests.list_requests(session, period, query)


@router.get("/options")
async def read_options(session: SessionDep) -> InternalOptions:
    return await internal_requests.list_options(session)


@router.get("/projects", responses=QUERY_ERRORS)
async def read_project_budgets(
    query: Annotated[ProjectRowsQuery, Query()], session: SessionDep
) -> ProjectBudgetPage:
    return await project_budgets.list_project_budgets(session, query)


@router.get("/projects/{project_id}", responses=DETAIL_ERRORS)
async def read_project_detail(
    project_id: ProjectIdPath,
    query: Annotated[ProjectMonthQuery, Query()],
    session: SessionDep,
) -> ProjectUsageDetail:
    detail = await project_detail.project_detail(session, project_id, query.month)
    if detail is None:
        raise _project_not_found()
    return detail


@router.put("/projects/{project_id}/budget", responses=SAVE_ERRORS)
async def save_budget(
    project_id: ProjectIdPath,
    body: ProjectBudgetSave,
    session: SessionDep,
    user: CurrentUserDep,
) -> ProjectBudgetRead:
    try:
        budget = await project_budget_save.save_project_budget(
            session,
            project_id,
            body.monthly_amount_usd,
            body.effective_from_month,
            user.user_id,
        )
    except ProjectNotFoundError as error:
        raise _project_not_found() from error
    except ProjectBudgetConflictError as error:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            ErrorCode.BUDGET_PERIOD_CONFLICT,
            BUDGET_CONFLICT_MESSAGE,
        ) from error
    return ProjectBudgetRead(
        budget_id=budget.budget_id,
        project_id=project_id,
        monthly_amount_usd=budget.monthly_amount_usd,
        effective_from_month=budget.effective_from_month,
        effective_to_month=budget.effective_to_month,
    )

"""내부 AI 예산 관리(P-02) 경로. 입력 검증과 응답 변환만 하고, 집계는 services/internal_usage가 한다.

로그인 검사는 팀 결정으로 뒤로 미뤘다(main.py). 복구할 때 이 라우터도 함께 대상이 된다.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import NowDep
from app.api.errors import ApiError
from app.api.usage import PERIOD_MESSAGES, QUERY_ERRORS
from app.db import SessionDep
from app.schemas.common import ErrorCode
from app.schemas.internal_usage import (
    InternalFilterQuery,
    InternalSummary,
    InternalTrend,
)
from app.schemas.project_budget import ProjectBudgetPage, ProjectRowsQuery
from app.services import internal_usage, project_budgets
from app.services.simulation_period import (
    DateRange,
    InvalidPeriodError,
    kst_today,
    resolve_period,
)

router = APIRouter(prefix="/usage/internal", tags=["internal-budget"])


def _period(query: InternalFilterQuery, today: date) -> DateRange:
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
    query: Annotated[InternalFilterQuery, Query()], session: SessionDep, now: NowDep
) -> InternalSummary:
    return await internal_usage.summarize(session, _period(query, kst_today(now)))


@router.get("/trend", responses=QUERY_ERRORS)
async def read_trend(
    query: Annotated[InternalFilterQuery, Query()], session: SessionDep, now: NowDep
) -> InternalTrend:
    return await internal_usage.daily_trend(session, _period(query, kst_today(now)))


@router.get("/projects", responses=QUERY_ERRORS)
async def read_project_budgets(
    query: Annotated[ProjectRowsQuery, Query()], session: SessionDep
) -> ProjectBudgetPage:
    return await project_budgets.list_project_budgets(session, query)

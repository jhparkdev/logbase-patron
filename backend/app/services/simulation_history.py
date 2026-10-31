"""이력 목록(S-08). 읽기만 한다.

정렬과 페이지는 화면이 한다(팀 결정). 서버는 조건으로 거른 결과를 고정된 순서로 상한까지 준다.
요약은 v_simulation_summary 가 계산한 값을 그대로 쓰고 여기서 다시 합산하지 않는다.
"""

from datetime import datetime

from sqlalchemy import ColumnElement, column, exists, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SimulationResult, SimulationRun
from app.schemas.simulation_history import (
    MAX_HISTORY_ITEMS,
    SimulationHistoryList,
    SimulationHistoryQuery,
)
from app.schemas.simulation_result import SimulationSummary
from app.services.simulation_period import (
    DateRange,
    kst_today,
    resolve_period,
    utc_bounds,
)

# 뷰의 열 이름은 요약 응답의 필드 이름과 같다(진행·결과 조회도 이 전제로 읽는다)
_SUMMARY = table(
    "v_simulation_summary", *(column(name) for name in SimulationSummary.model_fields)
)


def resolve_history_period(
    query: SimulationHistoryQuery, now: datetime
) -> DateRange | None:
    """조회할 KST 기간. 실행 ID 만으로 찾을 때는 기간으로 거르지 않는다(None).

    ID 를 아는 실행은 기본 30일보다 오래되었어도 찾을 수 있어야 하기 때문이다.
    날짜를 함께 보냈으면 그 날짜는 그대로 검증하고 적용한다.
    """
    no_dates = query.start_date is None and query.end_date is None
    if query.simulation_id is not None and no_dates:
        return None
    return resolve_period(query.start_date, query.end_date, kst_today(now))


async def list_simulation_history(
    session: AsyncSession, query: SimulationHistoryQuery, now: datetime
) -> SimulationHistoryList:
    conditions = _conditions(query, resolve_history_period(query, now))
    total = await session.scalar(
        select(func.count()).select_from(_SUMMARY).where(*conditions)
    )
    rows = await session.execute(
        select(_SUMMARY)
        .where(*conditions)
        .order_by(_SUMMARY.c.requested_at.desc(), _SUMMARY.c.simulation_id.desc())
        .limit(MAX_HISTORY_ITEMS)
    )
    items = [SimulationSummary.model_validate(dict(row)) for row in rows.mappings()]
    total = total or 0
    return SimulationHistoryList(items=items, total=total, truncated=total > len(items))


def _conditions(
    query: SimulationHistoryQuery, period: DateRange | None
) -> list[ColumnElement[bool]]:
    view = _SUMMARY.c
    conditions: list[ColumnElement[bool]] = []
    if period is not None:
        start, end = utc_bounds(period)
        conditions += [view.requested_at >= start, view.requested_at < end]
    if query.status is not None:
        conditions.append(view.status == query.status.value)
    if query.simulation_id is not None:
        conditions.append(view.simulation_id == query.simulation_id)
    if query.scenario_id is not None:
        # 뷰에는 시나리오 코드만 있어서 실행 행의 시나리오 ID 로 거른다
        conditions.append(
            exists().where(
                SimulationRun.simulation_id == view.simulation_id,
                SimulationRun.scenario_id == query.scenario_id,
            )
        )
    if query.model_id is not None:
        conditions.append(
            exists().where(
                SimulationResult.simulation_id == view.simulation_id,
                SimulationResult.model_id == query.model_id,
            )
        )
    return conditions

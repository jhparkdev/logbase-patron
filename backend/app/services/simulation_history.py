"""이력 목록(S-08). 읽기만 한다.

조건으로 거른 결과를 서버가 정렬하고 한 페이지씩 준다.
요약은 v_simulation_summary 가 계산한 값을 그대로 쓰고 여기서 다시 합산하지 않는다.
"""

from datetime import datetime

from sqlalchemy import ColumnElement, column, distinct, exists, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelRegistry, ModelStatus, SimulationResult, SimulationRun
from app.schemas.simulation_history import (
    HistorySortColumn,
    SimulationHistoryItem,
    SimulationHistoryList,
    SimulationHistoryQuery,
    SortDirection,
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


# 응답의 total_cost_usd 와 같은 값(확정 + 추정, 한쪽만 있으면 그 값, 둘 다 없으면 null).
# 뷰가 낸 두 합계를 더할 뿐이고, 없는 쪽을 0 으로 채우지 않는다
_TOTAL_COST = func.coalesce(
    _SUMMARY.c.confirmed_cost_usd + _SUMMARY.c.estimated_cost_usd,
    _SUMMARY.c.confirmed_cost_usd,
    _SUMMARY.c.estimated_cost_usd,
)

# 화면의 정렬 키 → v_simulation_summary 의 열(또는 열로 만든 값)
_SORT_COLUMNS: dict[HistorySortColumn, ColumnElement[object]] = {
    HistorySortColumn.REQUESTED_AT: _SUMMARY.c.requested_at,
    HistorySortColumn.ID: _SUMMARY.c.simulation_id,
    HistorySortColumn.SCENARIO: _SUMMARY.c.scenario_code,
    HistorySortColumn.MODEL_COUNT: _SUMMARY.c.model_count,
    HistorySortColumn.STATUS: _SUMMARY.c.status,
    HistorySortColumn.COST_STATUS: _SUMMARY.c.cost_check_status,
    HistorySortColumn.TOTAL_COST: _TOTAL_COST,
}


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
        select(_SUMMARY, _inactive_model_count())
        .where(*conditions)
        .order_by(*_ordering(query))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    items = [SimulationHistoryItem.model_validate(dict(row)) for row in rows.mappings()]
    return SimulationHistoryList(items=items, total=total or 0)


def _inactive_model_count() -> ColumnElement[int]:
    """행마다 지금 선택할 수 없는 모델 수. 선택 가능 기준은 is_model_selectable(ACTIVE 만)과 같다."""
    return (
        select(func.count(distinct(SimulationResult.model_id)))
        .join(ModelRegistry, ModelRegistry.model_id == SimulationResult.model_id)
        .where(
            SimulationResult.simulation_id == _SUMMARY.c.simulation_id,
            SimulationResult.is_final_attempt,
            ModelRegistry.status != ModelStatus.ACTIVE,
        )
        .scalar_subquery()
        .label("inactive_model_count")
    )


def _ordering(query: SimulationHistoryQuery) -> list[ColumnElement[object]]:
    column = _SORT_COLUMNS[query.sort]
    chosen = column.asc() if query.direction == SortDirection.ASC else column.desc()
    # 값이 없는 행(직접 작성 실행의 시나리오 등)은 방향과 관계없이 뒤로 보낸다.
    # 같은 값이면 실행 ID 로 순서를 고정해 페이지를 넘겨도 겹치거나 빠지지 않게 한다
    return [chosen.nulls_last(), _SUMMARY.c.simulation_id.desc()]


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

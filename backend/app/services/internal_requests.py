"""내부 호출 이력(P-02). 호출 이력(ai_requests)의 내부 출처 행을 표로 읽는다.

요약·추이와 같은 조건식(internal_usage.api_conditions)을 써서 같은 조건의 합계가 서로 일치한다.
"""

from typing import Any

from sqlalchemy import ColumnElement, Select, case, collate, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, ModelRegistry, Project, Service, Task
from app.schemas.internal_requests import (
    InternalOptions,
    InternalRequestPage,
    InternalRequestRow,
    InternalRequestSort,
    InternalRequestsQuery,
)
from app.schemas.models import SortOrder
from app.schemas.usage import UsageOption
from app.services.aggregation import (
    CODE_POINT_COLLATION,
    OTHER_TASK_TYPE_LABEL,
    REQUEST_PREVIEW_ROWS,
    TASK_TYPE_LABELS,
)
from app.services.internal_usage import INTERNAL_ORIGINS, api_conditions
from app.services.simulation_period import DateRange


def _by_name(column: Any) -> ColumnElement[str]:
    return collate(column, CODE_POINT_COLLATION)


def _conditions(period: DateRange, query: InternalRequestsQuery) -> list[Any]:
    conditions = api_conditions(period)
    if query.project_id is not None:
        conditions.append(AIRequest.project_id == query.project_id)
    if query.service_id is not None:
        conditions.append(AIRequest.service_id == query.service_id)
    if query.model_id is not None:
        conditions.append(AIRequest.model_id == query.model_id)
    return conditions


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
            AIRequest.usage_origin,
            AIRequest.project_id,
            Project.name.label("project_name"),
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
        .outerjoin(Project, Project.project_id == AIRequest.project_id)
        .outerjoin(Task, Task.task_id == AIRequest.task_id)
    )


def _request_order(query: InternalRequestsQuery) -> list[Any]:
    """값이 없는 행(미확인 비용 등)은 방향과 관계없이 맨 뒤다. 끝의 두 열로 순서를 고정한다."""
    columns: dict[InternalRequestSort, Any] = {
        InternalRequestSort.REQUESTED_AT: AIRequest.requested_at,
        InternalRequestSort.PROJECT: _by_name(Project.name),
        InternalRequestSort.SERVICE: _by_name(Service.name),
        InternalRequestSort.MODEL: _model_column(),
        InternalRequestSort.TASK_TYPE: _by_name(_task_type_label_column()),
        InternalRequestSort.TOKENS: _tokens_column(),
        InternalRequestSort.COST: AIRequest.cost_usd,
        InternalRequestSort.COST_STATUS: AIRequest.cost_status,
        InternalRequestSort.STATUS: AIRequest.status,
    }
    column = columns[query.sort]
    primary = column.desc() if query.order == SortOrder.DESC else column.asc()
    return [
        primary.nulls_last(),
        AIRequest.requested_at.desc(),
        AIRequest.request_id.desc(),
    ]


async def list_requests(
    session: AsyncSession, period: DateRange, query: InternalRequestsQuery
) -> InternalRequestPage:
    conditions = _conditions(period, query)
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
    return InternalRequestPage(
        items=[InternalRequestRow.model_validate(dict(row)) for row in rows.mappings()],
        total=total or 0,
        page=query.page,
        page_size=query.page_size,
    )


def _options(rows: Any) -> list[UsageOption]:
    return [UsageOption(id=row[0], name=row[1]) for row in rows]


async def list_options(session: AsyncSession) -> InternalOptions:
    projects = await session.execute(
        select(Project.project_id, Project.name)
        .where(Project.is_active)
        .order_by(_by_name(Project.name))
    )
    used_services = select(AIRequest.service_id).where(
        AIRequest.usage_origin.in_(INTERNAL_ORIGINS)
    )
    used_models = select(AIRequest.model_id).where(
        AIRequest.usage_origin.in_(INTERNAL_ORIGINS)
    )
    services = await session.execute(
        select(Service.service_id, Service.name)
        .where(Service.service_id.in_(used_services))
        .order_by(_by_name(Service.name))
    )
    models = await session.execute(
        select(ModelRegistry.model_id, ModelRegistry.display_name)
        .where(ModelRegistry.model_id.in_(used_models))
        .order_by(_by_name(ModelRegistry.display_name))
    )
    return InternalOptions(
        projects=_options(projects),
        services=_options(services),
        models=_options(models),
    )

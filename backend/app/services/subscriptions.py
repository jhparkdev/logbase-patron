"""월 구독료(P-02) 목록, 등록, 수정. 삭제는 없다: 그만 쓰는 구독은 status를 CANCELLED로 바꾼다.

구독 하나는 subscription_reference로 구분하고, 같은 구독은 매달 같은 값으로 한 행씩 등록한다.
해지(CANCELLED)는 "이 달을 끝으로 해지함" 표시일 뿐이라 그 달 금액은 집계에 그대로 들어간다.
수정은 바뀐 항목만 change_logs에 남긴다. 식별값, 도구 이름, 적용 월은 수정할 수 없다.
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import ColumnElement, collate, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChangeAction,
    ChangeLog,
    Project,
    SubscriptionCost,
    SubscriptionStatus,
)
from app.schemas.models import SortOrder
from app.schemas.subscription import (
    SubscriptionList,
    SubscriptionProject,
    SubscriptionRow,
    SubscriptionSort,
    SubscriptionsQuery,
)
from app.services.aggregation import CODE_POINT_COLLATION
from app.services.internal_usage import subscription_conditions
from app.services.simulation_period import DateRange

ENTITY_TYPE = "subscription_costs"
# 요약 화면의 미리보기 건수
SUBSCRIPTION_PREVIEW_ROWS = 5
CREATE_REASON = "구독료 등록"
UPDATE_REASON = "구독료 수정"
# 등록 값 이름 → subscription_costs 컬럼 이름. 이력에는 컬럼 이름으로 남긴다
CREATE_COLUMNS = {
    "subscription_reference": "subscription_reference",
    "tool_name": "tool_name",
    "subscription_type": "subscription_type",
    "applied_month": "applied_month",
    "amount_usd": "amount",
    "project_id": "project_id",
    "note": "note",
}
# 요청 필드 이름 → subscription_costs 컬럼 이름
EDITABLE_COLUMNS = {
    "amount_usd": "amount",
    "project_id": "project_id",
    "status": "status",
    "note": "note",
}


class SubscriptionNotFoundError(LookupError):
    """수정할 구독료가 없다."""


class SubscriptionProjectNotFoundError(LookupError):
    """배분하려는 프로젝트가 없다."""


class SubscriptionDuplicateError(ValueError):
    """같은 구독 식별값으로 같은 적용 월에 이미 등록되어 있다."""


def _row(subscription: SubscriptionCost, project_name: str | None) -> SubscriptionRow:
    return SubscriptionRow(
        subscription_id=subscription.subscription_id,
        subscription_reference=subscription.subscription_reference,
        tool_name=subscription.tool_name,
        subscription_type=subscription.subscription_type,
        applied_month=subscription.applied_month,
        amount_usd=subscription.amount,
        project_id=subscription.project_id,
        project_name=project_name,
        status=subscription.status,
        note=subscription.note,
    )


def _by_name(column: Any) -> ColumnElement[str]:
    return collate(column, CODE_POINT_COLLATION)


def _tie_breakers() -> list[Any]:
    return [
        _by_name(SubscriptionCost.tool_name).asc(),
        SubscriptionCost.subscription_id.asc(),
    ]


def _order(query: SubscriptionsQuery) -> list[Any]:
    """프로젝트에 배분하지 않은 구독료는 방향과 관계없이 프로젝트 정렬의 맨 뒤다. 끝의 두 열로 순서를 고정한다."""
    columns: dict[SubscriptionSort, Any] = {
        SubscriptionSort.TOOL: _by_name(SubscriptionCost.tool_name),
        SubscriptionSort.MONTH: SubscriptionCost.applied_month,
        SubscriptionSort.AMOUNT: SubscriptionCost.amount,
        SubscriptionSort.PROJECT: _by_name(Project.name),
        SubscriptionSort.STATUS: SubscriptionCost.status,
    }
    column = columns[query.sort]
    primary = column.desc() if query.order == SortOrder.DESC else column.asc()
    return [primary.nulls_last(), *_tie_breakers()]


async def list_subscriptions(
    session: AsyncSession, period: DateRange, query: SubscriptionsQuery
) -> SubscriptionList:
    """조회 기간이 걸치는 모든 달의 구독료. 해지된 것도 상태와 함께 나온다.

    요약의 구독료 합계와 같은 조건(internal_usage.subscription_conditions)을 써서 합계가 일치한다.
    """
    conditions = subscription_conditions(period, query.project_id)
    total = await session.scalar(
        select(func.count()).select_from(SubscriptionCost).where(*conditions)
    )
    statement = (
        select(SubscriptionCost, Project.name)
        .outerjoin(Project, Project.project_id == SubscriptionCost.project_id)
        .where(*conditions)
        .order_by(*_order(query))
    )
    if query.preview:
        # 적용 월이 최근인 N건을 먼저 고른다. 정렬해도 "최근 N건"의 뜻이 바뀌지 않게 하기 위해서다
        latest = (
            select(SubscriptionCost.subscription_id)
            .where(*conditions)
            .order_by(SubscriptionCost.applied_month.desc(), *_tie_breakers())
            .limit(SUBSCRIPTION_PREVIEW_ROWS)
        )
        statement = statement.where(SubscriptionCost.subscription_id.in_(latest))
    else:
        statement = statement.offset((query.page - 1) * query.page_size).limit(
            query.page_size
        )
    rows = await session.execute(statement)
    return SubscriptionList(
        items=[_row(subscription, name) for subscription, name in rows.all()],
        total=total or 0,
        page=query.page,
        page_size=query.page_size,
    )


async def get_subscription(
    session: AsyncSession, subscription_id: int
) -> SubscriptionRow | None:
    """번호로 구독료 한 건을 읽는다. 기간과 상관없이 찾고, 없으면 None이다."""
    result = await session.execute(
        select(SubscriptionCost, Project.name)
        .outerjoin(Project, Project.project_id == SubscriptionCost.project_id)
        .where(SubscriptionCost.subscription_id == subscription_id)
    )
    row = result.one_or_none()
    return None if row is None else _row(row[0], row[1])


async def list_project_options(session: AsyncSession) -> list[SubscriptionProject]:
    """구독료를 배분할 수 있는 프로젝트. 사용 중인 프로젝트만 이름순으로 준다."""
    result = await session.execute(
        select(Project.project_id, Project.name).where(Project.is_active)
    )
    return [
        SubscriptionProject(project_id=project_id, name=name)
        for project_id, name in sorted(result.all(), key=lambda row: (row[1], row[0]))
    ]


def _loggable(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if isinstance(value, Decimal) else value


async def _require_project(session: AsyncSession, project_id: int) -> None:
    exists = await session.scalar(
        select(Project.project_id).where(Project.project_id == project_id)
    )
    if exists is None:
        raise SubscriptionProjectNotFoundError


async def _project_name(session: AsyncSession, project_id: int | None) -> str | None:
    if project_id is None:
        return None
    return await session.scalar(
        select(Project.name).where(Project.project_id == project_id)
    )


async def create_subscription(
    session: AsyncSession, values: Mapping[str, Any], user_id: int
) -> SubscriptionRow:
    """구독료를 등록한다. 상태를 주지 않으면 진행 중(ACTIVE)이다. values는 SubscriptionCreate의 필드와 같다."""
    if values["project_id"] is not None:
        await _require_project(session, values["project_id"])
    duplicate = await session.scalar(
        select(SubscriptionCost.subscription_id).where(
            SubscriptionCost.subscription_reference == values["subscription_reference"],
            SubscriptionCost.applied_month == values["applied_month"],
        )
    )
    if duplicate is not None:
        raise SubscriptionDuplicateError
    columns = {column: values[name] for name, column in CREATE_COLUMNS.items()}
    status = SubscriptionStatus(values.get("status", SubscriptionStatus.ACTIVE)).value
    subscription = SubscriptionCost(
        **columns,
        status=status,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(subscription)
    try:
        await session.flush()
    except IntegrityError as error:
        # 위의 중복 확인과 저장 사이에 같은 구독이 먼저 들어간 경우다. 다른 제약은 입력 검증이 막는다
        await session.rollback()
        raise SubscriptionDuplicateError from error
    changes = {
        column: {"old": None, "new": _loggable(value)}
        for column, value in columns.items()
        if value is not None
    }
    changes["status"] = {"old": None, "new": status}
    session.add(
        ChangeLog(
            entity_type=ENTITY_TYPE,
            entity_id=str(subscription.subscription_id),
            action=ChangeAction.CREATE.value,
            changes=changes,
            reason=CREATE_REASON,
            changed_by=user_id,
        )
    )
    await session.commit()
    return _row(subscription, await _project_name(session, subscription.project_id))


async def update_subscription(
    session: AsyncSession,
    subscription_id: int,
    changes: Mapping[str, Any],
    user_id: int,
) -> SubscriptionRow:
    """보낸 항목만 바꾼다. 바뀐 값이 없으면 이력도 수정자도 남기지 않는다."""
    # 같은 구독료의 동시 수정을 줄 세운다
    subscription = await session.scalar(
        select(SubscriptionCost)
        .where(SubscriptionCost.subscription_id == subscription_id)
        .with_for_update()
    )
    if subscription is None:
        raise SubscriptionNotFoundError
    new_project_id = changes.get("project_id")
    if new_project_id is not None:
        await _require_project(session, new_project_id)
    diff: dict[str, Any] = {}
    for key, new in changes.items():
        column = EDITABLE_COLUMNS[key]
        value = new.value if isinstance(new, Enum) else new
        old = getattr(subscription, column)
        if old != value:
            setattr(subscription, column, value)
            diff[column] = {"old": _loggable(old), "new": _loggable(value)}
    if diff:
        subscription.updated_by = user_id
        session.add(
            ChangeLog(
                entity_type=ENTITY_TYPE,
                entity_id=str(subscription_id),
                action=ChangeAction.UPDATE.value,
                changes=diff,
                reason=UPDATE_REASON,
                changed_by=user_id,
            )
        )
    await session.commit()
    return _row(subscription, await _project_name(session, subscription.project_id))

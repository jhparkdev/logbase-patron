"""구독료 목록·수정 테스트. 수정은 바뀐 항목만 변경 이력(change_logs)에 남긴다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog, SubscriptionCost, SubscriptionStatus
from app.services.subscriptions import (
    SubscriptionDuplicateError,
    SubscriptionNotFoundError,
    SubscriptionProjectNotFoundError,
    create_subscription,
    list_project_options,
    list_subscriptions,
    update_subscription,
)
from tests.db_helpers import Factory

SEPTEMBER = date(2026, 9, 1)
OCTOBER = date(2026, 10, 1)


@pytest.fixture
async def user_id(factory: Factory) -> int:
    return (await factory.user())["user_id"]


def new_values(**values: Any) -> dict[str, Any]:
    """등록에 필요한 값. 프로젝트와 메모와 종류는 기본이 비어 있다."""
    return {
        "subscription_reference": "CommandCode_team1",
        "tool_name": "Command Code",
        "subscription_type": None,
        "applied_month": OCTOBER,
        "amount_usd": Decimal(20),
        "project_id": None,
        "note": None,
        **values,
    }


async def stored_of(session: AsyncSession) -> list[SubscriptionCost]:
    session.expire_all()
    return list(await session.scalars(select(SubscriptionCost)))


async def logs_of(session: AsyncSession, subscription_id: int) -> list[ChangeLog]:
    rows = await session.scalars(
        select(ChangeLog)
        .where(
            ChangeLog.entity_type == "subscription_costs",
            ChangeLog.entity_id == str(subscription_id),
        )
        .order_by(ChangeLog.log_id)
    )
    return list(rows)


async def reload(session: AsyncSession, subscription_id: int) -> SubscriptionCost:
    session.expire_all()
    row = await session.get(SubscriptionCost, subscription_id)
    assert row is not None
    return row


# ---------------------------------------------------------------
# 목록
# ---------------------------------------------------------------
async def test_목록은_그_달_구독료만_도구_이름순으로_프로젝트_이름과_함께_돌려준다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    await factory.subscription_cost(
        applied_month=OCTOBER, tool_name="나 도구", project_id=project["project_id"]
    )
    await factory.subscription_cost(applied_month=OCTOBER, tool_name="가 도구")
    await factory.subscription_cost(applied_month=SEPTEMBER, tool_name="다른 달")

    rows = await list_subscriptions(db_session, OCTOBER)

    assert [(row.tool_name, row.project_name) for row in rows] == [
        ("가 도구", None),
        ("나 도구", "알파"),
    ]
    assert rows[0].project_id is None
    assert rows[1].project_id == project["project_id"]


async def test_목록은_해지된_구독료도_상태와_함께_돌려준다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.subscription_cost(applied_month=OCTOBER, status="CANCELLED")

    rows = await list_subscriptions(db_session, OCTOBER)

    assert [row.status for row in rows] == [SubscriptionStatus.CANCELLED]


async def test_같은_이름의_도구는_등록_순서로_나온다(
    db_session: AsyncSession, factory: Factory
) -> None:
    first = await factory.subscription_cost(applied_month=OCTOBER, tool_name="같은")
    second = await factory.subscription_cost(applied_month=OCTOBER, tool_name="같은")

    rows = await list_subscriptions(db_session, OCTOBER)

    assert [row.subscription_id for row in rows] == [
        first["subscription_id"],
        second["subscription_id"],
    ]


async def test_구독료가_없는_달은_빈_목록이다(db_session: AsyncSession) -> None:
    assert await list_subscriptions(db_session, OCTOBER) == []


# ---------------------------------------------------------------
# 프로젝트 선택 목록
# ---------------------------------------------------------------
async def test_선택_목록은_사용_중인_프로젝트만_이름순으로_돌려준다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.project(name="나")
    await factory.project(name="가")
    await factory.project(name="중단됨", is_active=False)

    options = await list_project_options(db_session)

    assert [option.name for option in options] == ["가", "나"]


# ---------------------------------------------------------------
# 등록
# ---------------------------------------------------------------
async def test_등록하면_진행_중_상태로_저장하고_생성_이력을_남긴다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    project = await factory.project(name="알파")
    values = new_values(
        project_id=project["project_id"], subscription_type="Team", note="10월분"
    )

    row = await create_subscription(db_session, values, user_id)

    assert row.subscription_reference == "CommandCode_team1"
    assert row.tool_name == "Command Code"
    assert row.subscription_type == "Team"
    assert row.applied_month == OCTOBER
    assert row.amount_usd == Decimal(20)
    assert row.project_id == project["project_id"]
    assert row.project_name == "알파"
    assert row.status == SubscriptionStatus.ACTIVE
    assert row.note == "10월분"
    stored = (await stored_of(db_session))[0]
    assert stored.subscription_id == row.subscription_id
    assert stored.status == "ACTIVE"
    assert stored.currency == "USD"
    assert stored.created_by == user_id
    assert stored.updated_by == user_id
    logs = await logs_of(db_session, row.subscription_id)
    assert [log.action for log in logs] == ["CREATE"]
    assert logs[0].changed_by == user_id
    assert logs[0].changes["subscription_reference"] == {
        "old": None,
        "new": "CommandCode_team1",
    }
    assert logs[0].changes["applied_month"] == {"old": None, "new": "2026-10-01"}
    assert Decimal(logs[0].changes["amount"]["new"]) == Decimal(20)


async def test_프로젝트를_정하지_않으면_미배분으로_저장한다(
    db_session: AsyncSession, user_id: int
) -> None:
    row = await create_subscription(db_session, new_values(), user_id)

    assert row.project_id is None
    assert row.project_name is None
    assert (await stored_of(db_session))[0].project_id is None


async def test_같은_식별값이어도_다른_달이면_등록된다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    await factory.subscription_cost(
        subscription_reference="CommandCode_team1", applied_month=SEPTEMBER
    )

    await create_subscription(db_session, new_values(), user_id)

    assert len(await stored_of(db_session)) == 2


async def test_식별값이_다르면_같은_도구와_같은_달도_등록된다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    await factory.subscription_cost(
        subscription_reference="CommandCode_team2",
        tool_name="Command Code",
        applied_month=OCTOBER,
    )

    await create_subscription(db_session, new_values(), user_id)

    assert len(await stored_of(db_session)) == 2


async def test_같은_식별값과_같은_달은_거절하고_이력도_남기지_않는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    existing = await factory.subscription_cost(
        subscription_reference="CommandCode_team1",
        applied_month=OCTOBER,
        amount=Decimal(10),
    )

    with pytest.raises(SubscriptionDuplicateError):
        await create_subscription(db_session, new_values(), user_id)

    stored = await stored_of(db_session)
    assert len(stored) == 1
    assert stored[0].subscription_id == existing["subscription_id"]
    assert stored[0].amount == Decimal(10)
    assert await logs_of(db_session, existing["subscription_id"]) == []


async def test_없는_프로젝트로는_등록할_수_없다(
    db_session: AsyncSession, user_id: int
) -> None:
    with pytest.raises(SubscriptionProjectNotFoundError):
        await create_subscription(db_session, new_values(project_id=987654), user_id)

    assert await stored_of(db_session) == []


# ---------------------------------------------------------------
# 수정
# ---------------------------------------------------------------
async def test_금액을_바꾸면_바뀐_항목만_이력에_남는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    created = await factory.subscription_cost(amount=Decimal(10))

    row = await update_subscription(
        db_session, created["subscription_id"], {"amount_usd": Decimal("12.5")}, user_id
    )

    assert row.amount_usd == Decimal("12.5")
    stored = await reload(db_session, created["subscription_id"])
    assert stored.amount == Decimal("12.5")
    assert stored.updated_by == user_id
    logs = await logs_of(db_session, created["subscription_id"])
    assert [log.action for log in logs] == ["UPDATE"]
    assert logs[0].changed_by == user_id
    assert set(logs[0].changes) == {"amount"}
    assert Decimal(logs[0].changes["amount"]["old"]) == Decimal(10)
    assert Decimal(logs[0].changes["amount"]["new"]) == Decimal("12.5")


async def test_여러_항목을_한_번에_바꾸면_이력_한_건에_모두_담긴다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    project = await factory.project(name="알파")
    created = await factory.subscription_cost(note=None)
    changes = {
        "status": SubscriptionStatus.CANCELLED,
        "project_id": project["project_id"],
        "note": "해지함",
    }

    row = await update_subscription(
        db_session, created["subscription_id"], changes, user_id
    )

    assert row.status == SubscriptionStatus.CANCELLED
    assert row.project_name == "알파"
    assert row.note == "해지함"
    logs = await logs_of(db_session, created["subscription_id"])
    assert len(logs) == 1
    assert logs[0].changes == {
        "status": {"old": "ACTIVE", "new": "CANCELLED"},
        "project_id": {"old": None, "new": project["project_id"]},
        "note": {"old": None, "new": "해지함"},
    }


async def test_프로젝트를_null로_바꾸면_미배분이_된다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    project = await factory.project()
    created = await factory.subscription_cost(project_id=project["project_id"])

    row = await update_subscription(
        db_session, created["subscription_id"], {"project_id": None}, user_id
    )

    assert row.project_id is None
    assert row.project_name is None
    assert (await reload(db_session, created["subscription_id"])).project_id is None


async def test_바뀐_것이_없으면_이력도_수정자도_남기지_않는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    created = await factory.subscription_cost(amount=Decimal(10))

    await update_subscription(
        db_session,
        created["subscription_id"],
        {"amount_usd": Decimal(10), "status": SubscriptionStatus.ACTIVE},
        user_id,
    )

    assert await logs_of(db_session, created["subscription_id"]) == []
    assert (await reload(db_session, created["subscription_id"])).updated_by is None


async def test_금액은_0까지_허용한다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    created = await factory.subscription_cost(amount=Decimal(10))

    row = await update_subscription(
        db_session, created["subscription_id"], {"amount_usd": Decimal(0)}, user_id
    )

    assert row.amount_usd == 0


async def test_다른_구독료는_건드리지_않는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    target = await factory.subscription_cost(amount=Decimal(10))
    other = await factory.subscription_cost(amount=Decimal(10))

    await update_subscription(
        db_session, target["subscription_id"], {"amount_usd": Decimal(99)}, user_id
    )

    assert (await reload(db_session, other["subscription_id"])).amount == Decimal(10)
    assert await logs_of(db_session, other["subscription_id"]) == []


async def test_없는_구독료는_거절한다(db_session: AsyncSession, user_id: int) -> None:
    with pytest.raises(SubscriptionNotFoundError):
        await update_subscription(db_session, 987654, {"note": "x"}, user_id)


async def test_없는_프로젝트로는_바꿀_수_없고_아무것도_바뀌지_않는다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    created = await factory.subscription_cost(amount=Decimal(10))

    with pytest.raises(SubscriptionProjectNotFoundError):
        await update_subscription(
            db_session,
            created["subscription_id"],
            {"amount_usd": Decimal(99), "project_id": 987654},
            user_id,
        )

    assert (await reload(db_session, created["subscription_id"])).amount == Decimal(10)
    assert await logs_of(db_session, created["subscription_id"]) == []

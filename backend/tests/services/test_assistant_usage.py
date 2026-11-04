from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest
from app.schemas.assistant import AssistantPageContext
from app.schemas.assistant_usage import CustomerUsageToolQuery, InternalUsageToolQuery
from app.schemas.usage import UsageOption
from app.services.assistant_usage import (
    AssistantUsage,
    UsageQueryError,
    entity_id,
    usage_period,
)
from tests.db_helpers import Factory
from tests.internal_budget_helpers import internal_call

NOW = datetime(2026, 11, 3, tzinfo=UTC)


def test_explicit_all_customers_clears_stale_model_arguments_only_for_that_filter() -> (
    None
):
    options = [UsageOption(id=1, name="로웰린 스튜디오")]
    assert (
        entity_id(options, 1, "로웰린 스튜디오", 1, "고객", "10월 전체 고객 비용")
        is None
    )
    assert entity_id(options, None, None, 1, "모델", "10월 전체 고객 비용") == 1


@pytest.mark.parametrize(
    ("text", "arguments", "expected"),
    [
        ("선택한 고객 비용", {"period": "this_month"}, ("2026-10-01", "2026-10-31")),
        (
            "선택한 고객 비용",
            {"start_date": "2026-11-01", "end_date": "2026-11-03"},
            ("2026-10-01", "2026-10-31"),
        ),
        ("10월 비용", {"period": "this_month"}, ("2026-10-01", "2026-10-31")),
        ("2024년 2월 비용", {}, ("2024-02-01", "2024-02-29")),
        ("2026-10-12부터 2026-10-15까지 비용", {}, ("2026-10-12", "2026-10-15")),
        ("10월 12일부터 10월 15일까지 비용", {}, ("2026-10-12", "2026-10-15")),
        ("이번 달 비용", {}, ("2026-11-01", "2026-11-03")),
        ("최근 7일 비용", {}, ("2026-10-28", "2026-11-03")),
    ],
)
def test_period_is_derived_from_user_and_screen_not_guessed_model_arguments(
    text: str, arguments: dict[str, str], expected: tuple[str, str]
) -> None:
    context = AssistantPageContext(
        page="customer_usage", start_date="2026-10-01", end_date="2026-10-31"
    )
    actual = usage_period(
        CustomerUsageToolQuery(**arguments), context, NOW, text, internal=False
    )
    assert (actual.start.isoformat(), actual.end.isoformat()) == expected


def test_period_default_does_not_take_unrelated_screen_or_model_guessed_today() -> None:
    actual = usage_period(
        CustomerUsageToolQuery(period="today"), None, NOW, "최근 호출", internal=False
    )
    assert actual.start.isoformat() == "2026-10-05"
    assert actual.end.isoformat() == "2026-11-03"


def test_period_bounds_and_korean_midnight_are_preserved() -> None:
    query = CustomerUsageToolQuery()
    now = datetime(2026, 10, 31, 15, tzinfo=UTC)
    actual = usage_period(query, None, now, "이번 달 비용", internal=False)
    assert actual.start.isoformat() == actual.end.isoformat() == "2026-11-01"
    for text in (
        "최근 367일 비용",
        "2026-02-30 비용",
        "2024-01-01부터 2025-01-01까지 비용",
    ):
        with pytest.raises(UsageQueryError):
            usage_period(query, None, NOW, text, internal=False)


async def customer_call(
    factory: Factory, customer_id: int, **values: object
) -> RowMapping:
    key = await factory.api_key(owner_type="CUSTOMER", customer_id=customer_id)
    service = await factory.service(service_type="CUSTOMER_FACING")
    return await factory.ai_request(
        usage_origin="CUSTOMER_SERVICE",
        customer_id=customer_id,
        key_id=key["key_id"],
        service_id=service["service_id"],
        requested_at=datetime(2026, 10, 25, 8, tzinfo=UTC),
        **values,
    )


async def test_customer_calls_use_name_and_never_include_internal_or_simulations(
    db_session: AsyncSession, factory: Factory
) -> None:
    customer = await factory.customer(name="가상고객A (패션)")
    expected = await customer_call(factory, customer["customer_id"])
    await internal_call(factory)
    await factory.ai_request(usage_origin="SIMULATION")
    count = await db_session.scalar(select(func.count()).select_from(AIRequest))
    tool = AssistantUsage(db_session, NOW, None, "가상고객A의 최근 호출을 알려줘")
    result, source = await tool.customer(
        CustomerUsageToolQuery(customer_name="가상고객A", section="requests")
    )
    assert [row["request_id"] for row in result["data"]["items"]] == [
        str(expected["request_id"])
    ]
    assert result["data"]["items"][0]["cost_usd"] is None
    assert source.kind == "customer_usage"
    assert source.page_context.customer_id == customer["customer_id"]
    assert await db_session.scalar(select(func.count()).select_from(AIRequest)) == count


async def test_context_filters_apply_but_explicit_customer_and_relative_period_win(
    db_session: AsyncSession, factory: Factory
) -> None:
    a = await factory.customer(name="고객 A")
    b = await factory.customer(name="고객 B")
    context = AssistantPageContext(
        page="customer_usage",
        start_date="2026-10-01",
        end_date="2026-10-31",
        customer_id=a["customer_id"],
    )
    tool = AssistantUsage(db_session, NOW, context, "고객 B의 이번 달 비용")
    _, source = await tool.customer(CustomerUsageToolQuery(customer_name="고객 B"))
    assert source.page_context.customer_id == b["customer_id"]
    assert source.page_context.start_date.isoformat() == "2026-11-01"
    assert source.page_context.end_date.isoformat() == "2026-11-03"


async def test_user_named_customer_is_respected_even_if_model_omits_or_changes_it(
    db_session: AsyncSession, factory: Factory
) -> None:
    a = await factory.customer(name="가상고객A (패션)")
    b = await factory.customer(name="가상고객B (가전)")
    context = AssistantPageContext(page="customer_usage", customer_id=a["customer_id"])
    tool = AssistantUsage(db_session, NOW, context, "가상고객B의 비용을 알려줘")
    _, source = await tool.customer(CustomerUsageToolQuery())
    assert source.page_context.customer_id == b["customer_id"]
    with pytest.raises(UsageQueryError):
        await tool.customer(CustomerUsageToolQuery(customer_id=a["customer_id"]))
    tool = AssistantUsage(db_session, NOW, context, "현재 조건의 비용을 알려줘")
    with pytest.raises(UsageQueryError):
        await tool.customer(CustomerUsageToolQuery(customer_name="가상고객B"))
    tool = AssistantUsage(db_session, NOW, context, "전체 고객의 비용을 알려줘")
    _, source = await tool.customer(CustomerUsageToolQuery())
    assert source.page_context.customer_id is None
    _, source = await tool.customer(CustomerUsageToolQuery(customer_name="가상고객A"))
    assert source.page_context.customer_id is None


async def test_budget_overrun_request_is_filtered_even_if_model_omits_status(
    db_session: AsyncSession, factory: Factory
) -> None:
    for amount in ("1", "101"):
        customer = await factory.customer()
        await factory.budget(
            scope_type="CUSTOMER",
            customer_id=customer["customer_id"],
            monthly_amount_usd=Decimal(100),
        )
        await customer_call(
            factory,
            customer["customer_id"],
            cost_status="CONFIRMED",
            cost_usd=Decimal(amount),
            cost_source="API_RESPONSE",
        )
    tool = AssistantUsage(
        db_session,
        NOW,
        AssistantPageContext(
            page="customer_usage", start_date="2026-10-01", end_date="2026-10-31"
        ),
        "예산을 초과한 고객만 보여줘",
    )
    result, source = await tool.customer(CustomerUsageToolQuery(section="budgets"))
    assert source.page_context.budget_status == "OVER"
    assert result["data"]["total"] == 1


async def test_ambiguous_or_unknown_names_do_not_silently_select_an_entity(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.customer(name="가상고객A")
    await factory.customer(name="가상고객B")
    tool = AssistantUsage(db_session, NOW, None, "고객 비용")
    for name in ["가상고객", "없는 고객"]:
        with pytest.raises(UsageQueryError):
            await tool.customer(CustomerUsageToolQuery(customer_name=name))


async def test_internal_query_does_not_inherit_customer_filters_and_reuses_totals(
    db_session: AsyncSession, factory: Factory
) -> None:
    project = await factory.project(name="내부 프로젝트 A")
    await internal_call(
        factory, project_id=project["project_id"], cost_usd=Decimal("2.123456789012")
    )
    await factory.subscription_cost(
        project_id=project["project_id"], amount=Decimal(10)
    )
    customer = await factory.customer(name="고객 A")
    await customer_call(
        factory,
        customer["customer_id"],
        cost_status="CONFIRMED",
        cost_usd=Decimal(99),
        cost_source="API_RESPONSE",
    )
    tool = AssistantUsage(
        db_session,
        NOW,
        AssistantPageContext(
            page="customer_usage",
            start_date="2026-10-20",
            end_date="2026-10-21",
            customer_id=customer["customer_id"],
        ),
        "내부 프로젝트 A의 10월 비용",
    )
    result, source = await tool.internal(
        InternalUsageToolQuery(
            project_name="내부 프로젝트 A",
            start_date="2026-10-01",
            end_date="2026-10-31",
        )
    )
    assert Decimal(result["data"]["api_confirmed_usd"]) == Decimal("2.123456789012")
    assert Decimal(result["data"]["subscription_usd"]) == Decimal(10)
    assert Decimal(result["data"]["total_managed_usd"]) == Decimal("12.123456789012")
    assert source.page_context.project_id == project["project_id"]


async def test_page_context_and_period_validation_remain_bounded(
    db_session: AsyncSession,
) -> None:
    tool = AssistantUsage(db_session, NOW, None, "고객 사용량")
    with pytest.raises(UsageQueryError):
        await tool.customer(CustomerUsageToolQuery(start_date="2026-01-01"))
    with pytest.raises(UsageQueryError):
        await tool.customer(
            CustomerUsageToolQuery(start_date="2024-01-01", end_date="2026-01-01")
        )

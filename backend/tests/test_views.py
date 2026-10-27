"""첫 마이그레이션이 만드는 집계 뷰 2개(v_request_facts, v_simulation_summary)의 결과 테스트.

뷰는 models.py가 아니라 마이그레이션 SQL로 만들어지므로 test_models.py와 따로 둔다.
mock 데이터 기대 합계와의 대조는 feature/db-seed에서 한다. 여기서는 테스트가 직접 넣은 몇 행으로 로직만 본다.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.db_helpers import Factory


async def _request_fact(session: AsyncSession, request_id: uuid.UUID) -> RowMapping:
    result = await session.execute(
        text("SELECT * FROM v_request_facts WHERE request_id = :id"), {"id": request_id}
    )
    return result.mappings().one()


async def _simulation_summary(
    session: AsyncSession, simulation_id: uuid.UUID
) -> RowMapping:
    result = await session.execute(
        text("SELECT * FROM v_simulation_summary WHERE simulation_id = :id"),
        {"id": simulation_id},
    )
    return result.mappings().one()


# ---------------------------------------------------------------------------
# v_request_facts: 공통 집계 뷰
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requested_at", "kst_date", "kst_month"),
    [
        # KST 월 경계(11월 1일 00:00 KST = 10월 31일 15:00 UTC)의 바로 전, 정확히 그 값, 바로 후
        (
            datetime(2026, 10, 31, 14, 59, 59, 999999, tzinfo=UTC),
            date(2026, 10, 31),
            date(2026, 10, 1),
        ),
        (
            datetime(2026, 10, 31, 15, 0, 0, tzinfo=UTC),
            date(2026, 11, 1),
            date(2026, 11, 1),
        ),
        (
            datetime(2026, 10, 31, 15, 0, 0, 1, tzinfo=UTC),
            date(2026, 11, 1),
            date(2026, 11, 1),
        ),
    ],
)
async def test_request_date_and_month_follow_kst(
    factory: Factory,
    db_session: AsyncSession,
    requested_at: datetime,
    kst_date: date,
    kst_month: date,
) -> None:
    """UTC로 저장된 호출 시각을 KST 날짜·월(그 달 1일)로 바꿔 보여 준다."""
    request = await factory.ai_request(requested_at=requested_at)

    fact = await _request_fact(db_session, request["request_id"])

    assert fact["kst_date"] == kst_date
    assert fact["kst_month"] == kst_month


async def test_cost_is_split_by_cost_status(
    factory: Factory, db_session: AsyncSession
) -> None:
    """확정·추정 비용을 따로 보여 주고, 미확인은 0이 아니라 비워 두고 표시만 한다."""
    price_id = (await factory.model_price())["price_id"]
    confirmed = await factory.ai_request(
        cost_status="CONFIRMED", cost_usd=Decimal("1.5")
    )
    estimated = await factory.ai_request(
        cost_status="ESTIMATED", cost_usd=Decimal("0.25"), price_id=price_id
    )
    unknown = await factory.ai_request(cost_status="UNKNOWN", cost_usd=None)

    confirmed_fact = await _request_fact(db_session, confirmed["request_id"])
    estimated_fact = await _request_fact(db_session, estimated["request_id"])
    unknown_fact = await _request_fact(db_session, unknown["request_id"])

    assert (
        confirmed_fact["confirmed_cost_usd"],
        confirmed_fact["estimated_cost_usd"],
    ) == (Decimal("1.5"), None)
    assert (
        estimated_fact["confirmed_cost_usd"],
        estimated_fact["estimated_cost_usd"],
    ) == (None, Decimal("0.25"))
    assert (unknown_fact["confirmed_cost_usd"], unknown_fact["estimated_cost_usd"]) == (
        None,
        None,
    )
    assert unknown_fact["is_cost_unknown"] is True
    assert confirmed_fact["is_cost_unknown"] is False


async def test_customer_usage_without_customer_is_unclassified(
    factory: Factory, db_session: AsyncSession
) -> None:
    """고객을 알 수 없는 고객 호출만 미분류로 표시한다. 내부 호출은 미분류가 아니다."""
    customer = await factory.customer()
    unclassified = await factory.ai_request(
        usage_origin="CUSTOMER_SERVICE", customer_id=None
    )
    classified = await factory.ai_request(
        usage_origin="CUSTOMER_SERVICE", customer_id=customer["customer_id"]
    )
    internal = await factory.ai_request(usage_origin="INTERNAL_DEVELOPMENT")

    assert (await _request_fact(db_session, unclassified["request_id"]))[
        "is_customer_unclassified"
    ] is True
    assert (await _request_fact(db_session, classified["request_id"]))[
        "is_customer_unclassified"
    ] is False
    assert (await _request_fact(db_session, internal["request_id"]))[
        "is_customer_unclassified"
    ] is False


async def test_request_fact_joins_reference_names(
    factory: Factory, db_session: AsyncSession
) -> None:
    """고객·서비스·모델의 코드와 이름을 함께 보여 준다."""
    customer = await factory.customer()
    service = await factory.service()
    model = await factory.model()
    request = await factory.ai_request(
        usage_origin="CUSTOMER_SERVICE",
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
        model_id=model["model_id"],
    )

    fact = await _request_fact(db_session, request["request_id"])

    assert (fact["customer_code"], fact["customer_name"]) == (
        customer["customer_code"],
        customer["name"],
    )
    assert (fact["service_code"], fact["service_name"]) == (
        service["service_code"],
        service["name"],
    )
    assert fact["model_display_name"] == model["display_name"]
    assert fact["owner_type"] == "CUSTOMER"


# ---------------------------------------------------------------------------
# v_simulation_summary: 시뮬레이션 실행별 요약 (P-05)
# ---------------------------------------------------------------------------


async def _add_result(
    factory: Factory,
    simulation_id: uuid.UUID,
    slot_no: int,
    *,
    status: str = "SUCCESS",
    cost_status: str = "CONFIRMED",
    cost_usd: Decimal = Decimal(1),
    is_final_attempt: bool = True,
) -> None:
    """실행에 모델 결과 하나(호출 + 결과 행)를 붙인다."""
    extra: dict[str, object] = {}
    if status in ("FAILED", "TIMEOUT"):
        extra["error_type"] = "PROVIDER_ERROR"
    if cost_status == "ESTIMATED":
        extra["price_id"] = (await factory.model_price())["price_id"]
    request = await factory.ai_request(
        usage_origin="SIMULATION",
        simulation_id=simulation_id,
        status=status,
        cost_status=cost_status,
        cost_usd=None if cost_status == "UNKNOWN" else cost_usd,
        **extra,
    )
    await factory.simulation_result(
        simulation_id=simulation_id,
        request_id=request["request_id"],
        slot_no=slot_no,
        is_final_attempt=is_final_attempt,
    )


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([], "확인 중"),
        ([("SUCCESS", "CONFIRMED"), ("RUNNING", "UNKNOWN")], "확인 중"),
        ([("SUCCESS", "CONFIRMED"), ("FAILED", "UNKNOWN")], "미확인 포함"),
        ([("SUCCESS", "CONFIRMED"), ("SUCCESS", "ESTIMATED")], "추정 포함"),
        ([("SUCCESS", "CONFIRMED"), ("FAILED", "CONFIRMED")], "확정"),
    ],
    ids=["no-results", "running", "unknown", "estimated", "confirmed"],
)
async def test_cost_check_status(
    factory: Factory,
    db_session: AsyncSession,
    results: list[tuple[str, str]],
    expected: str,
) -> None:
    """비용 확인 상태: 실행 중 → 확인 중, 미확인 있음 → 미확인 포함, 추정 있음 → 추정 포함, 모두 확정 → 확정."""
    simulation_id = (await factory.simulation_run())["simulation_id"]
    for slot_no, (status, cost_status) in enumerate(results, start=1):
        await _add_result(
            factory, simulation_id, slot_no, status=status, cost_status=cost_status
        )

    summary = await _simulation_summary(db_session, simulation_id)

    assert summary["cost_check_status"] == expected


async def test_summary_counts_final_results_and_sums_all_attempt_costs(
    factory: Factory, db_session: AsyncSession
) -> None:
    """성공·실패 수는 최종 결과만 세고, 비용 합계는 재시도 전 시도까지 모두 더한다(재시도도 비용이 나가므로)."""
    simulation_id = (await factory.simulation_run(model_count=3))["simulation_id"]
    await _add_result(factory, simulation_id, 1, cost_usd=Decimal("1.0"))
    await _add_result(
        factory,
        simulation_id,
        2,
        status="FAILED",
        cost_usd=Decimal("0.5"),
        is_final_attempt=False,
    )
    await _add_result(
        factory, simulation_id, 2, cost_status="ESTIMATED", cost_usd=Decimal("0.25")
    )
    await _add_result(
        factory, simulation_id, 3, status="TIMEOUT", cost_status="UNKNOWN"
    )

    summary = await _simulation_summary(db_session, simulation_id)

    assert summary["final_result_count"] == 3
    assert summary["success_count"] == 2
    assert summary["failure_count"] == 1
    assert summary["confirmed_cost_usd"] == Decimal("1.5")
    assert summary["estimated_cost_usd"] == Decimal("0.25")
    assert summary["unknown_cost_count"] == 1
    assert summary["cost_check_status"] == "미확인 포함"

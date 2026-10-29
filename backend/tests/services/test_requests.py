"""호출 상태를 조건부로 바꾸고, 먼저 확정된 종료 결과를 보존하는지 검증한다."""

import uuid
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CostSource, CostStatus, ErrorType, RequestStatus
from app.services import requests
from tests.db_helpers import T0, Factory, expect_rejected
from tests.services.request_helpers import FinishedRecord

FINISHED_AT = T0 + timedelta(seconds=42)
TERMINAL = {
    RequestStatus.SUCCESS,
    RequestStatus.FAILED,
    RequestStatus.TIMEOUT,
    RequestStatus.CANCELLED,
}


async def read_request(session: AsyncSession, request_id: uuid.UUID) -> RowMapping:
    result = await session.execute(
        text("SELECT * FROM ai_requests WHERE request_id = :id"), {"id": request_id}
    )
    return result.mappings().one()


def error_for(status: RequestStatus) -> ErrorType | None:
    if status == RequestStatus.FAILED:
        return ErrorType.PROVIDER_ERROR
    if status == RequestStatus.TIMEOUT:
        return ErrorType.TIMEOUT_ERROR
    return None


@pytest.mark.parametrize("status", list(RequestStatus))
async def test_start_changes_only_pending_requests(
    factory: Factory, db_session: AsyncSession, status: RequestStatus
) -> None:
    before = await factory.ai_request(status=status, error_type=error_for(status))

    changed = await requests.mark_running(db_session, before["request_id"], T0)

    after = await read_request(db_session, before["request_id"])
    assert changed is (status == RequestStatus.PENDING)
    if changed:
        assert after["status"] == RequestStatus.RUNNING
        # 시작 시각 전용 컬럼이 없으므로 원래 요청 시각을 덮어쓰지 않는다.
        assert after["requested_at"] == before["requested_at"]
        assert after["completed_at"] is None
        assert not await requests.mark_running(db_session, before["request_id"], T0)
    else:
        assert after == before


@pytest.mark.parametrize(
    "status", [RequestStatus.SUCCESS, RequestStatus.FAILED, RequestStatus.TIMEOUT]
)
async def test_finish_records_status_and_result_in_one_transition(
    factory: Factory, db_session: AsyncSession, status: RequestStatus
) -> None:
    before = await factory.ai_request(status="RUNNING")
    record = replace(FinishedRecord(), status=status, error_type=error_for(status))

    assert await requests.record_finished(
        db_session,
        before["request_id"],
        record,
        FINISHED_AT,
        cost_source=CostSource.API_RESPONSE,
    )

    after = await read_request(db_session, before["request_id"])
    for column in (
        "status",
        "error_type",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "cost_status",
        "actual_provider",
        "actual_model",
        "latency_ms",
        "external_generation_id",
    ):
        assert after[column] == getattr(record, column)
    assert after["cost_source"] == CostSource.API_RESPONSE
    assert after["cost_confirmed_at"] == FINISHED_AT
    assert after["completed_at"] == FINISHED_AT
    assert after["requested_at"] == before["requested_at"]
    assert not await requests.cancel_request(
        db_session, before["request_id"], FINISHED_AT
    )
    assert await read_request(db_session, before["request_id"]) == after


@pytest.mark.parametrize("status", [RequestStatus.PENDING, *TERMINAL])
async def test_late_finish_does_not_overwrite_any_request_fields(
    factory: Factory, db_session: AsyncSession, status: RequestStatus
) -> None:
    before = await factory.ai_request(
        status=status,
        error_type=error_for(status),
        completed_at=FINISHED_AT if status in TERMINAL else None,
        cost_status="CONFIRMED",
        cost_usd=Decimal("0.03"),
        cost_source="MANUAL",
        input_tokens=5,
        actual_provider="original-provider",
    )

    assert not await requests.record_finished(
        db_session, before["request_id"], FinishedRecord(), FINISHED_AT
    )
    # 상태뿐 아니라 비용·토큰·업체·updated_at까지 모든 컬럼이 보존되는지 비교한다.
    assert await read_request(db_session, before["request_id"]) == before


@pytest.mark.parametrize("status", list(RequestStatus))
async def test_cancel_changes_only_pending_or_running_requests(
    factory: Factory, db_session: AsyncSession, status: RequestStatus
) -> None:
    before = await factory.ai_request(
        status=status,
        error_type=error_for(status),
        external_generation_id="gen-preserve-for-reconciliation",
    )

    changed = await requests.cancel_request(
        db_session, before["request_id"], FINISHED_AT
    )

    after = await read_request(db_session, before["request_id"])
    assert changed is (status in {RequestStatus.PENDING, RequestStatus.RUNNING})
    if changed:
        assert after["status"] == RequestStatus.CANCELLED
        assert after["error_type"] is None
        assert after["cost_status"] == CostStatus.UNKNOWN
        assert after["cost_usd"] is None
        assert after["cost_source"] is None
        assert after["completed_at"] == FINISHED_AT
        assert after["external_generation_id"] == before["external_generation_id"]
        assert not await requests.cancel_request(
            db_session, before["request_id"], FINISHED_AT
        )
        assert await read_request(db_session, before["request_id"]) == after
    else:
        assert after == before


@pytest.mark.parametrize(
    "method", ["mark_running", "record_finished", "cancel_request"]
)
async def test_missing_request_returns_false(
    db_session: AsyncSession, method: str
) -> None:
    function = getattr(requests, method)
    args = (
        (FinishedRecord(), FINISHED_AT)
        if method == "record_finished"
        else (FINISHED_AT,)
    )
    assert not await function(db_session, uuid.uuid4(), *args)


@pytest.mark.parametrize("cost", [None, Decimal(0), Decimal("0.05")])
async def test_finish_persists_cost_without_classifying_its_source(
    factory: Factory, db_session: AsyncSession, cost: Decimal | None
) -> None:
    """확정 0원도 근거를 임의로 붙이지 않는다. 비용 판별은 호출 측의 책임이다."""
    before = await factory.ai_request(status="RUNNING")
    status = CostStatus.UNKNOWN if cost is None else CostStatus.CONFIRMED
    record = replace(FinishedRecord(), cost_status=status, cost_usd=cost)

    assert await requests.record_finished(
        db_session, before["request_id"], record, FINISHED_AT
    )

    after = await read_request(db_session, before["request_id"])
    assert after["cost_status"] == status
    assert after["cost_usd"] == cost
    assert after["cost_source"] is None
    assert after["cost_confirmed_at"] == (None if cost is None else FINISHED_AT)


@pytest.mark.parametrize(
    "status", [RequestStatus.PENDING, RequestStatus.RUNNING, RequestStatus.CANCELLED]
)
async def test_finish_rejects_statuses_that_need_a_different_operation(
    factory: Factory, db_session: AsyncSession, status: RequestStatus
) -> None:
    before = await factory.ai_request(status="RUNNING")
    with pytest.raises(ValueError, match="SUCCESS.*FAILED.*TIMEOUT"):
        await requests.record_finished(
            db_session,
            before["request_id"],
            replace(FinishedRecord(), status=status),
            FINISHED_AT,
        )
    assert await read_request(db_session, before["request_id"]) == before


@pytest.mark.parametrize(
    "method", ["mark_running", "record_finished", "cancel_request"]
)
async def test_transition_rejects_a_time_without_timezone(
    factory: Factory, db_session: AsyncSession, method: str
) -> None:
    before = await factory.ai_request(status="RUNNING")
    naive = FINISHED_AT.replace(tzinfo=None)
    args = (FinishedRecord(), naive) if method == "record_finished" else (naive,)
    with pytest.raises(ValueError, match="시간대"):
        await getattr(requests, method)(db_session, before["request_id"], *args)
    assert await read_request(db_session, before["request_id"]) == before


async def test_invalid_result_rolls_back_the_whole_transition(
    factory: Factory, db_session: AsyncSession
) -> None:
    # 토큰 제약이 거절되면 같은 UPDATE의 상태·금액 변경도 함께 취소되어야 한다.
    before = await factory.ai_request(status="RUNNING")
    await expect_rejected(
        db_session,
        requests.record_finished(
            db_session,
            before["request_id"],
            replace(FinishedRecord(), input_tokens=-1),
            FINISHED_AT,
        ),
        constraint="ai_requests_input_tokens_check",
    )
    assert await read_request(db_session, before["request_id"]) == before


@pytest.mark.parametrize("method", ["record_finished", "cancel_request"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
async def test_completion_time_is_not_before_the_request(
    factory: Factory, db_session: AsyncSession, method: str, offset: int
) -> None:
    """요청 시각의 1마이크로초 전·정확히 같음·1마이크로초 후로 종료 시각 경계를 검사한다."""
    before = await factory.ai_request(status="RUNNING")
    now = T0 + timedelta(microseconds=offset)
    args = (FinishedRecord(), now) if method == "record_finished" else (now,)
    operation = getattr(requests, method)(db_session, before["request_id"], *args)
    if offset < 0:
        await expect_rejected(db_session, operation, constraint="ck_ai_requests_period")
        assert await read_request(db_session, before["request_id"]) == before
    else:
        assert await operation
        after = await read_request(db_session, before["request_id"])
        assert after["completed_at"] == now


async def test_finish_persists_a_supplied_estimate_and_its_price_reference(
    factory: Factory, db_session: AsyncSession
) -> None:
    before = await factory.ai_request(status="RUNNING")
    price = await factory.model_price()
    record = replace(FinishedRecord(), cost_status=CostStatus.ESTIMATED)

    assert await requests.record_finished(
        db_session,
        before["request_id"],
        record,
        FINISHED_AT,
        cost_source=CostSource.PRICE_ESTIMATE,
        price_id=price["price_id"],
    )

    after = await read_request(db_session, before["request_id"])
    assert after["cost_usd"] == record.cost_usd
    assert after["cost_status"] == CostStatus.ESTIMATED
    assert after["cost_source"] == CostSource.PRICE_ESTIMATE
    assert after["price_id"] == price["price_id"]
    assert after["cost_confirmed_at"] is None

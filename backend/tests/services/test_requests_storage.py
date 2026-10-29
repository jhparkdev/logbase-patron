"""호출 전 이력 생성과 원문 저장이 기존 데이터를 보존하는지 검증한다."""

import uuid
from dataclasses import fields, replace
from datetime import timedelta

import pytest
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CallPurpose, DataSource, UsageOrigin
from app.services import requests
from tests.db_helpers import T0, Factory, expect_rejected
from tests.services.request_helpers import FinishedRecord, PendingRecord

MESSAGES: list[dict[str, JsonValue]] = [
    {"role": "system", "content": "한국어로 답해주세요."},
    {"role": "user", "content": "요약할 본문입니다."},
]


@pytest.fixture
async def pending_record(factory: Factory) -> PendingRecord:
    # 참조할 시뮬레이션·모델·서비스부터 만들어 외래키 조건을 만족하는 입력을 준비한다.
    simulation = await factory.simulation_run()
    model = await factory.model()
    service = await factory.service()
    return PendingRecord(
        request_id=uuid.uuid4(),
        simulation_id=simulation["simulation_id"],
        usage_origin=UsageOrigin.SIMULATION,
        call_purpose=CallPurpose.EXPERIMENT,
        attempt_no=1,
        project_id=simulation["project_id"],
        key_id=simulation["key_id"],
        service_id=service["service_id"],
        executed_by=simulation["executed_by"],
        model_id=model["model_id"],
        requested_model=model["openrouter_model_id"],
        requested_provider="pinned-provider",
        routing_policy={"allow_fallbacks": False, "order": ["pinned-provider"]},
        execution_config={"temperature": 0.7, "max_tokens": 512},
        input_hash="a" * 64,
        requested_at=T0,
        data_source=DataSource.LIVE,
    )


async def test_create_pending_preserves_the_supplied_identifiers_and_configuration(
    db_session: AsyncSession, pending_record: PendingRecord
) -> None:
    assert await requests.create_pending(db_session, pending_record) is None

    row = (
        (
            await db_session.execute(
                text("SELECT * FROM ai_requests WHERE request_id = :id"),
                {"id": pending_record.request_id},
            )
        )
        .mappings()
        .one()
    )
    for field in fields(pending_record):
        assert row[field.name] == getattr(pending_record, field.name)
    assert row["status"] == "PENDING"
    assert row["cost_status"] == "UNKNOWN"
    assert row["cost_usd"] is None
    assert row["cost_source"] is None
    assert row["completed_at"] is None
    assert row["error_type"] is None


async def test_duplicate_creation_does_not_reset_a_finished_request(
    db_session: AsyncSession, pending_record: PendingRecord
) -> None:
    await requests.create_pending(db_session, pending_record)
    assert await requests.mark_running(db_session, pending_record.request_id, T0)
    assert await requests.record_finished(
        db_session,
        pending_record.request_id,
        FinishedRecord(),
        T0 + timedelta(seconds=42),
    )
    query = text("SELECT * FROM ai_requests WHERE request_id = :id")
    before = (
        (await db_session.execute(query, {"id": pending_record.request_id}))
        .mappings()
        .one()
    )

    await expect_rejected(
        db_session,
        requests.create_pending(db_session, pending_record),
        constraint="ai_requests_pkey",
    )

    assert (
        await db_session.execute(query, {"id": pending_record.request_id})
    ).mappings().one() == before


async def test_invalid_simulation_is_not_silently_replaced_or_created(
    db_session: AsyncSession, pending_record: PendingRecord
) -> None:
    await expect_rejected(
        db_session,
        requests.create_pending(
            db_session, replace(pending_record, simulation_id=uuid.uuid4())
        ),
        constraint="ai_requests_simulation_id_fkey",
    )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM ai_requests WHERE request_id = :id"),
            {"id": pending_record.request_id},
        )
        == 0
    )


async def test_create_pending_rejects_a_time_without_timezone(
    db_session: AsyncSession, pending_record: PendingRecord
) -> None:
    with pytest.raises(ValueError, match="시간대"):
        await requests.create_pending(
            db_session, replace(pending_record, requested_at=T0.replace(tzinfo=None))
        )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM ai_requests WHERE request_id = :id"),
            {"id": pending_record.request_id},
        )
        == 0
    )


@pytest.mark.parametrize("response", [None, "", "한국어 응답입니다."])
async def test_payload_keeps_the_message_array_and_response_without_changing_status(
    factory: Factory, db_session: AsyncSession, response: str | None
) -> None:
    before = await factory.ai_request(status="CANCELLED")

    assert (
        await requests.save_payload(
            db_session, before["request_id"], MESSAGES, response
        )
        is None
    )

    payload = (
        (
            await db_session.execute(
                text("SELECT * FROM ai_request_payloads WHERE request_id = :id"),
                {"id": before["request_id"]},
            )
        )
        .mappings()
        .one()
    )
    assert payload["request_messages"] == MESSAGES
    assert payload["response_text"] == response
    assert payload["response_raw"] is None
    assert (
        await db_session.execute(
            text("SELECT * FROM ai_requests WHERE request_id = :id"),
            {"id": before["request_id"]},
        )
    ).mappings().one() == before


async def test_payload_supports_structured_image_asset_references(
    factory: Factory, db_session: AsyncSession
) -> None:
    request = await factory.ai_request()
    messages: list[dict[str, JsonValue]] = [
        {"role": "user", "content": [{"type": "image", "asset_id": str(uuid.uuid4())}]}
    ]
    await requests.save_payload(db_session, request["request_id"], messages, None)
    assert (
        await db_session.scalar(
            text(
                "SELECT request_messages FROM ai_request_payloads WHERE request_id = :id"
            ),
            {"id": request["request_id"]},
        )
        == messages
    )


async def test_duplicate_payload_does_not_overwrite_the_original(
    factory: Factory, db_session: AsyncSession
) -> None:
    # 기존 원문을 새 입력과 다른 형태로 준비해, 중복 저장이 내용을 덮어쓰지 않는지 확인한다.
    request = await factory.ai_request()
    original = await factory.ai_request_payload(
        request_id=request["request_id"],
        request_messages={"original": True},
        response_text="원래 응답",
        response_raw={"original": True},
    )
    await expect_rejected(
        db_session,
        requests.save_payload(db_session, request["request_id"], MESSAGES, "다른 응답"),
        constraint="ai_request_payloads_pkey",
    )
    assert (
        await db_session.execute(
            text("SELECT * FROM ai_request_payloads WHERE request_id = :id"),
            {"id": request["request_id"]},
        )
    ).mappings().one() == original


async def test_payload_requires_an_existing_request(db_session: AsyncSession) -> None:
    await expect_rejected(
        db_session,
        requests.save_payload(db_session, uuid.uuid4(), MESSAGES, None),
        constraint="ai_request_payloads_request_id_fkey",
    )


async def test_pending_and_payload_writes_can_be_rolled_back_together(
    db_session: AsyncSession, pending_record: PendingRecord
) -> None:
    """접수 후속 작업이 실패해도 호출 이력이나 원문만 따로 남지 않아야 한다."""

    class RollbackProbe(Exception):
        pass

    with pytest.raises(RollbackProbe):
        async with db_session.begin_nested():
            await requests.create_pending(db_session, pending_record)
            await requests.save_payload(
                db_session, pending_record.request_id, MESSAGES, None
            )
            raise RollbackProbe

    for table in ("ai_requests", "ai_request_payloads"):
        assert (
            await db_session.scalar(
                text(f"SELECT count(*) FROM {table} WHERE request_id = :id"),
                {"id": pending_record.request_id},
            )
            == 0
        )

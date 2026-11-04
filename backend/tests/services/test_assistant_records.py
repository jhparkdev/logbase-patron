from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest
from app.services.assistant_records import (
    ASSISTANT_SERVICE_CODE,
    STALE_AFTER,
    AssistantContextMissingError,
    close_stale_calls,
    find_call_context,
)
from tests.connection_helpers import MODEL_ID
from tests.db_helpers import Factory


async def poc_project_and_key(factory: Factory) -> tuple[int, int]:
    project = await factory.project(project_code="PRJ-PATRON-POC", project_type="POC")
    key = await factory.api_key(
        project_id=project["project_id"], secret_ref="OPENROUTER_KEY_POC"
    )
    return project["project_id"], key["key_id"]


async def test_시뮬레이터와_같은_PoC_Key와_도우미_서비스와_등록_모델로_귀속한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    project_id, key_id = await poc_project_and_key(factory)
    service = await factory.service(
        service_code=ASSISTANT_SERVICE_CODE, service_type="PATRON"
    )
    model = await factory.model(openrouter_model_id=MODEL_ID)

    context = await find_call_context(db_session, MODEL_ID)

    assert (context.project_id, context.key_id, context.service_id) == (
        project_id,
        key_id,
        service["service_id"],
    )
    assert context.model_id == model["model_id"]
    assert context.openrouter_model == MODEL_ID


@pytest.mark.parametrize(
    ("parameters", "supports"),
    [(["tools", "temperature", "max_tokens"], True), (["tools", "max_tokens"], False)],
)
async def test_등록_모델의_지원_파라미터로_temperature를_보낼지_정한다(
    db_session: AsyncSession,
    factory: Factory,
    parameters: list[str],
    supports: bool,
) -> None:
    await poc_project_and_key(factory)
    await factory.service(service_code=ASSISTANT_SERVICE_CODE, service_type="PATRON")
    await factory.model(openrouter_model_id=MODEL_ID, supported_parameters=parameters)

    context = await find_call_context(db_session, MODEL_ID)

    assert context.supports_temperature is supports


async def test_등록하지_않은_모델이어도_호출_모델_이름으로_기록한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await poc_project_and_key(factory)
    await factory.service(service_code=ASSISTANT_SERVICE_CODE, service_type="PATRON")

    context = await find_call_context(db_session, "vendor/not-registered")

    # 지원 여부를 모르는 모델에 보내면 처리할 업체가 없어 실패할 수 있다.
    assert context.supports_temperature is False
    assert context.model_id is None
    assert context.openrouter_model == "vendor/not-registered"


@pytest.mark.parametrize("missing", ["service", "key"])
async def test_비용을_귀속할_대상이_없으면_호출하지_않도록_알린다(
    db_session: AsyncSession, factory: Factory, missing: str
) -> None:
    if missing == "service":
        await poc_project_and_key(factory)
    else:
        await factory.service(
            service_code=ASSISTANT_SERVICE_CODE, service_type="PATRON"
        )

    with pytest.raises(AssistantContextMissingError):
        await find_call_context(db_session, MODEL_ID)


NOW = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("age", "closed"),
    [
        (STALE_AFTER - timedelta(seconds=1), False),
        (STALE_AFTER, True),
        (STALE_AFTER + timedelta(seconds=1), True),
    ],
)
async def test_오래_열려_있는_도우미_호출만_취소로_닫는다(
    db_session: AsyncSession, factory: Factory, age: timedelta, closed: bool
) -> None:
    row = await factory.ai_request(
        usage_origin="ASSISTANT", status="RUNNING", requested_at=NOW - age
    )

    count = await close_stale_calls(db_session, NOW)

    saved = await db_session.get(AIRequest, row["request_id"])
    assert saved is not None
    assert count == (1 if closed else 0)
    assert saved.status == ("CANCELLED" if closed else "RUNNING")
    assert saved.cost_usd is None


async def test_다른_출처와_이미_끝난_호출은_건드리지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    old = NOW - STALE_AFTER - timedelta(minutes=1)
    simulation = await factory.ai_request(
        usage_origin="SIMULATION", status="RUNNING", requested_at=old
    )
    finished = await factory.ai_request(
        usage_origin="ASSISTANT",
        status="SUCCESS",
        requested_at=old,
        cost_status="CONFIRMED",
        cost_usd=Decimal("0.01"),
        cost_source="API_RESPONSE",
    )

    assert await close_stale_calls(db_session, NOW) == 0

    for row, status in ((simulation, "RUNNING"), (finished, "SUCCESS")):
        saved = await db_session.get(AIRequest, row["request_id"])
        assert saved is not None
        assert saved.status == status

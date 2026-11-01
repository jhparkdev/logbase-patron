import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, AIRequestPayload, ModelRegistry
from app.openrouter.errors import ErrorType
from app.openrouter.result import CallStatus
from app.services.model_test import (
    DEFAULT_PROMPT,
    TEST_MAX_TOKENS,
    TEST_TIMEOUT_SECONDS,
    ConnectionContextMissingError,
    ConnectionTestOutcome,
    ModelNotFoundError,
    run_connection_test,
)
from tests.connection_helpers import (
    LATENCY,
    MODEL_ID,
    NOW,
    FakeCaller,
    failure,
    success,
)
from tests.db_helpers import Factory

PROMPT = "테스트 문장"


@dataclass(frozen=True)
class Ready:
    """연결 테스트를 받을 준비가 된 DB: 시뮬레이터와 같은 PoC 프로젝트·Key, 연결 테스트 서비스, 관리자, 모델."""

    user_id: int
    model_id: int
    project_id: int
    key_id: int
    service_id: int


@pytest.fixture
async def ready(factory: Factory) -> Ready:
    project = await factory.project(project_code="PRJ-PATRON-POC", project_type="POC")
    service = await factory.service(
        service_code="PATRON_MODEL_TEST", service_type="PATRON"
    )
    key = await factory.api_key(
        project_id=project["project_id"], secret_ref="OPENROUTER_KEY_POC"
    )
    user = await factory.user()
    model = await factory.model(openrouter_model_id=MODEL_ID, provider="vendor")
    return Ready(
        user_id=user["user_id"],
        model_id=model["model_id"],
        project_id=project["project_id"],
        key_id=key["key_id"],
        service_id=service["service_id"],
    )


async def run(
    session: AsyncSession,
    caller: FakeCaller,
    ready: Ready,
    prompt: str | None = PROMPT,
) -> ConnectionTestOutcome:
    return await run_connection_test(
        session,
        caller,
        model_id=ready.model_id,
        prompt=prompt,
        user_id=ready.user_id,
        now=NOW,
    )


async def stored_request(session: AsyncSession) -> AIRequest:
    request = await session.scalar(select(AIRequest))
    assert request is not None
    return request


async def stored_model(session: AsyncSession, model_id: int) -> ModelRegistry:
    model = await session.scalar(
        select(ModelRegistry).where(ModelRegistry.model_id == model_id)
    )
    assert model is not None
    return model


async def count(session: AsyncSession, table: Any) -> int:
    return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_성공하면_호출_이력에_연결_테스트로_기록한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    await run(db_session, FakeCaller(success()), ready)

    request = await stored_request(db_session)
    assert request.usage_origin == "SYSTEM_TEST"
    assert request.call_purpose == "TEST"
    assert request.simulation_id is None
    assert request.executed_by == ready.user_id
    assert request.project_id == ready.project_id
    assert request.key_id == ready.key_id
    assert request.service_id == ready.service_id
    assert request.model_id == ready.model_id
    assert request.requested_model == MODEL_ID
    assert request.requested_provider == "auto"
    assert request.data_source == "LIVE"
    assert request.requested_at == NOW
    assert request.input_hash == hashlib.sha256(PROMPT.encode()).hexdigest()
    assert request.execution_config == {
        "max_tokens": TEST_MAX_TOKENS,
        "stream": True,
        "timeout_seconds": TEST_TIMEOUT_SECONDS,
    }


async def test_성공하면_결과_토큰_비용_업체를_기록한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    await run(db_session, FakeCaller(success()), ready)

    request = await stored_request(db_session)
    assert request.status == "SUCCESS"
    assert request.error_type is None
    assert request.input_tokens == 18
    assert request.output_tokens == 2
    assert request.cost_usd == Decimal("0.000001")
    assert request.cost_status == "CONFIRMED"
    assert request.cost_source == "API_RESPONSE"
    assert request.actual_provider == "Io Net"
    assert request.actual_model == MODEL_ID
    assert request.external_generation_id == "gen-test-1"
    assert request.latency_ms == 850
    assert request.completed_at == NOW + LATENCY


async def test_호출하기_전에_RUNNING으로_저장해_둔다(
    db_session: AsyncSession, ready: Ready
) -> None:
    caller = FakeCaller(success(), session=db_session)

    await run(db_session, caller, ready)

    assert caller.status_at_call == "RUNNING"


async def test_모델_ID와_메시지와_제한을_정해_호출한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    caller = FakeCaller(success())

    await run(db_session, caller, ready)

    [call] = caller.calls
    assert call["model_id"] == MODEL_ID
    assert call["messages"] == [{"role": "user", "content": PROMPT}]
    assert call["max_tokens"] == TEST_MAX_TOKENS
    assert call["timeout_seconds"] == TEST_TIMEOUT_SECONDS
    assert call["stream"] is True


async def test_문장이_없으면_기본_문장으로_호출한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    caller = FakeCaller(success())

    await run(db_session, caller, ready, prompt=None)

    assert caller.calls[0]["messages"] == [{"role": "user", "content": DEFAULT_PROMPT}]


async def test_요청과_응답_원문은_저장하지_않는다(
    db_session: AsyncSession, ready: Ready
) -> None:
    await run(db_session, FakeCaller(success()), ready)

    assert await count(db_session, AIRequestPayload) == 0


async def test_성공하면_모델의_마지막_테스트와_성공_시각을_갱신한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    await run(db_session, FakeCaller(success()), ready)

    model = await stored_model(db_session, ready.model_id)
    request = await stored_request(db_session)
    assert model.last_test_status == "SUCCESS"
    assert model.last_test_at == NOW + LATENCY
    assert model.last_test_request_id == request.request_id
    assert model.last_success_test_at == NOW + LATENCY


async def test_실패하면_마지막_테스트만_갱신하고_성공_시각은_그대로_둔다(
    db_session: AsyncSession, ready: Ready
) -> None:
    earlier = NOW - 5 * LATENCY
    await db_session.execute(
        update(ModelRegistry)
        .where(ModelRegistry.model_id == ready.model_id)
        .values(last_success_test_at=earlier)
    )
    caller = FakeCaller(failure(CallStatus.FAILED, ErrorType.AUTH_ERROR))

    outcome = await run(db_session, caller, ready)

    assert outcome.status == "FAILED"
    model = await stored_model(db_session, ready.model_id)
    assert model.last_test_status == "FAILED"
    assert model.last_test_at == NOW + LATENCY
    assert model.last_success_test_at == earlier


async def test_실패한_호출은_오류_종류와_비용_미확인으로_기록한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    caller = FakeCaller(failure(CallStatus.FAILED, ErrorType.AUTH_ERROR))

    outcome = await run(db_session, caller, ready)

    request = await stored_request(db_session)
    assert request.status == "FAILED"
    assert request.error_type == "AUTH_ERROR"
    assert request.cost_status == "UNKNOWN"
    assert request.cost_usd is None
    assert outcome.error_type == "AUTH_ERROR"
    assert outcome.error_message == "OpenRouter 인증에 실패했습니다."
    assert outcome.cost_usd is None
    assert outcome.cost_status == "UNKNOWN"


async def test_시간_초과는_TIMEOUT으로_기록한다(
    db_session: AsyncSession, ready: Ready
) -> None:
    caller = FakeCaller(failure(CallStatus.TIMEOUT, ErrorType.TIMEOUT_ERROR))

    outcome = await run(db_session, caller, ready)

    assert outcome.status == "TIMEOUT"
    assert (await stored_request(db_session)).status == "TIMEOUT"
    model = await stored_model(db_session, ready.model_id)
    assert model.last_test_status == "TIMEOUT"


async def test_결과에_화면에_보일_값을_담는다(
    db_session: AsyncSession, ready: Ready
) -> None:
    outcome = await run(db_session, FakeCaller(success()), ready)

    assert outcome == ConnectionTestOutcome(
        status="SUCCESS",
        tested_at=NOW + LATENCY,
        latency_ms=850,
        input_tokens=18,
        output_tokens=2,
        cost_usd=Decimal("0.000001"),
        cost_status="CONFIRMED",
        actual_provider="Io Net",
        error_type=None,
        error_message=None,
    )


async def test_없는_모델은_호출하지_않는다(
    db_session: AsyncSession, ready: Ready
) -> None:
    caller = FakeCaller(success())

    with pytest.raises(ModelNotFoundError):
        await run_connection_test(
            db_session,
            caller,
            model_id=999999,
            prompt=PROMPT,
            user_id=ready.user_id,
            now=NOW,
        )

    assert caller.calls == []
    assert await count(db_session, AIRequest) == 0


async def test_귀속_정보가_없으면_호출하지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    user = await factory.user()
    model = await factory.model()
    caller = FakeCaller(success())

    with pytest.raises(ConnectionContextMissingError):
        await run_connection_test(
            db_session,
            caller,
            model_id=model["model_id"],
            prompt=PROMPT,
            user_id=user["user_id"],
            now=NOW,
        )

    assert caller.calls == []
    assert await count(db_session, AIRequest) == 0

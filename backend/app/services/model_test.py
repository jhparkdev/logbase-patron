"""모델 연결 테스트(P-03). 호출 이력(SYSTEM_TEST)을 남기고 모델의 마지막 테스트 정보를 갱신한다.

호출하기 전에 이력을 RUNNING으로 저장(commit)해 두고, 끝난 뒤 결과를 기록한다.
요청·응답 원문은 저장하지 않는다.
"""

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    APIKey,
    CallPurpose,
    ConnectionTestStatus,
    CostSource,
    CostStatus,
    DataSource,
    ErrorType,
    KeyStatus,
    ModelRegistry,
    Project,
    RequestStatus,
    Service,
    UsageOrigin,
)
from app.openrouter.result import CallResult, CallStatus
from app.services import requests
from app.services.model_update import ModelNotFoundError
from app.services.simulation_lookup import (
    SIMULATOR_KEY_SECRET_REF,
    SIMULATOR_PROJECT_CODE,
)

# 시뮬레이터와 같은 PoC 프로젝트·Key를 쓰고, 서비스만 연결 테스트 전용이다. 값은 DB 담당 seed와 같다.
TEST_SERVICE_CODE = "PATRON_MODEL_TEST"
DEFAULT_PROMPT = "연결 확인용 요청입니다. '확인'이라고만 답해 주세요."
# 추론 모델은 답을 쓰기 전에 추론 토큰을 많이 써서, 작게 잡으면 내용 없이 끝나 실패로 보인다.
TEST_MAX_TOKENS = 1000
# 모델당 응답 대기시간(팀 결정)
TEST_TIMEOUT_SECONDS = 180.0
# 업체를 지정하지 않고 OpenRouter가 고르게 둔다는 뜻이다.
AUTO_PROVIDER = "auto"


class ConnectionContextMissingError(LookupError):
    """연결 테스트의 비용 귀속 대상(PoC 프로젝트·사용 중인 Key·테스트 서비스)이 DB에 없다. 운영 설정 문제다."""


class ConnectionCaller(Protocol):
    """openrouter/client.py의 call_model에서 연결 테스트가 쓰는 인자. 실패해도 예외 없이 결과로 돌려준다."""

    async def __call__(
        self,
        *,
        request_id: uuid.UUID,
        model_id: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        timeout_seconds: float,
        stream: bool,
    ) -> CallResult: ...


@dataclass(frozen=True)
class ConnectionTestOutcome:
    """화면에 보일 테스트 결과."""

    status: ConnectionTestStatus
    tested_at: datetime
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    cost_status: CostStatus
    actual_provider: str | None
    error_type: ErrorType | None
    error_message: str | None


@dataclass(frozen=True)
class _Context:
    project_id: int
    key_id: int
    service_id: int


@dataclass(frozen=True)
class _PendingTest:
    """requests.create_pending이 기대하는 모양(PendingRequest)의 연결 테스트 호출."""

    request_id: uuid.UUID
    project_id: int
    key_id: int
    service_id: int
    executed_by: int
    model_id: int
    requested_model: str
    input_hash: str
    requested_at: datetime
    execution_config: Mapping[str, JsonValue]
    simulation_id: None = None
    usage_origin: UsageOrigin = UsageOrigin.SYSTEM_TEST
    call_purpose: CallPurpose = CallPurpose.TEST
    attempt_no: int = 1
    requested_provider: str = AUTO_PROVIDER
    routing_policy: Mapping[str, JsonValue] = field(default_factory=dict)
    data_source: DataSource = DataSource.LIVE


@dataclass(frozen=True)
class _FinishedTest:
    """requests.record_finished가 기대하는 모양(RequestResult)의 종료 결과."""

    status: RequestStatus
    error_type: ErrorType | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    cost_status: CostStatus
    actual_provider: str | None
    actual_model: str | None
    latency_ms: int | None
    external_generation_id: str | None


async def run_connection_test(
    session: AsyncSession,
    caller: ConnectionCaller,
    *,
    model_id: int,
    prompt: str | None,
    user_id: int,
    now: datetime,
) -> ConnectionTestOutcome:
    """모델을 한 번 호출해 연결을 확인한다. 호출이 실패해도 예외가 아니라 결과로 돌려준다."""
    model = await session.get(ModelRegistry, model_id)
    if model is None:
        raise ModelNotFoundError
    context = await _find_context(session)

    text = prompt or DEFAULT_PROMPT
    request_id = uuid.uuid4()
    await requests.create_pending(
        session,
        _PendingTest(
            request_id=request_id,
            project_id=context.project_id,
            key_id=context.key_id,
            service_id=context.service_id,
            executed_by=user_id,
            model_id=model_id,
            requested_model=model.openrouter_model_id,
            input_hash=hashlib.sha256(text.encode()).hexdigest(),
            requested_at=now,
            execution_config={
                "max_tokens": TEST_MAX_TOKENS,
                "stream": True,
                "timeout_seconds": TEST_TIMEOUT_SECONDS,
            },
        ),
    )
    await requests.mark_running(session, request_id, now)
    # 외부 호출 전에 이력을 확정해 둔다. 호출 도중 서버가 멈춰도 호출 ID가 남는다.
    await session.commit()

    result = await caller(
        request_id=request_id,
        model_id=model.openrouter_model_id,
        messages=[{"role": "user", "content": text}],
        max_tokens=TEST_MAX_TOKENS,
        timeout_seconds=TEST_TIMEOUT_SECONDS,
        stream=True,
    )

    record = _finished(result)
    tested_at = now + timedelta(milliseconds=result.latency_ms)
    await requests.record_finished(
        session,
        request_id,
        record,
        tested_at,
        cost_source=_cost_source(result),
    )
    model.last_test_status = ConnectionTestStatus(result.status.value)
    model.last_test_at = tested_at
    model.last_test_request_id = request_id
    if result.status == CallStatus.SUCCESS:
        model.last_success_test_at = tested_at
    await session.commit()

    return ConnectionTestOutcome(
        status=ConnectionTestStatus(result.status.value),
        tested_at=tested_at,
        latency_ms=record.latency_ms,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cost_usd=record.cost_usd,
        cost_status=record.cost_status,
        actual_provider=record.actual_provider,
        error_type=record.error_type,
        error_message=result.error_message,
    )


async def _find_context(session: AsyncSession) -> _Context:
    row = (
        await session.execute(
            select(Project.project_id, APIKey.key_id, Service.service_id)
            .join(APIKey, APIKey.project_id == Project.project_id)
            .join(Service, Service.service_code == TEST_SERVICE_CODE)
            .where(
                Project.project_code == SIMULATOR_PROJECT_CODE,
                APIKey.secret_ref == SIMULATOR_KEY_SECRET_REF,
                APIKey.status == KeyStatus.ACTIVE,
            )
        )
    ).one_or_none()
    if row is None:
        raise ConnectionContextMissingError
    return _Context(
        project_id=row.project_id, key_id=row.key_id, service_id=row.service_id
    )


def _finished(result: CallResult) -> _FinishedTest:
    return _FinishedTest(
        status=RequestStatus(result.status.value),
        error_type=ErrorType(result.error_type.value) if result.error_type else None,
        input_tokens=result.prompt_tokens,
        output_tokens=result.completion_tokens,
        cost_usd=result.cost_usd,
        cost_status=CostStatus(result.cost_status.value),
        actual_provider=result.provider,
        actual_model=result.actual_model,
        latency_ms=result.latency_ms,
        external_generation_id=result.generation_id,
    )


def _cost_source(result: CallResult) -> CostSource | None:
    return CostSource(result.cost_source.value) if result.cost_source else None

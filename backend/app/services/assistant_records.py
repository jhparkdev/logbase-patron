"""AI 도우미의 OpenRouter 호출을 호출 이력(ASSISTANT)으로 남긴다.

호출 한 번마다 한 행이다. 외부 호출 전에 RUNNING으로 확정해 두어, 호출 도중 서버가 멈춰도 이력이 남는다.
요청·응답 원문은 저장하지 않는다. 대화에 고객 데이터가 섞이기 때문이다.
"""

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    APIKey,
    CallPurpose,
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
from app.openrouter.result import CallResult
from app.services import requests
from app.services.model_parameters import parameter_support
from app.services.model_test import AUTO_PROVIDER
from app.services.simulation_lookup import (
    SIMULATOR_KEY_SECRET_REF,
    SIMULATOR_PROJECT_CODE,
)

# 도우미 호출을 귀속하는 서비스. 시뮬레이터와 같은 PoC 프로젝트·Key를 쓰고 서비스로 구분한다.
ASSISTANT_SERVICE_CODE = "PATRON_ASSISTANT"
# 요청 전체 제한(120초)보다 넉넉히 둔다. 이보다 오래 열린 호출은 기다리는 요청이 없다.
STALE_AFTER = timedelta(minutes=5)


class AssistantContextMissingError(LookupError):
    """도우미 비용을 귀속할 PoC 프로젝트·사용 중인 Key·도우미 서비스가 DB에 없다."""


@dataclass(frozen=True)
class AssistantCallContext:
    project_id: int
    key_id: int
    service_id: int
    # 등록하지 않은 모델이면 None이다. 호출 모델 이름은 requested_model로 남는다.
    model_id: int | None
    openrouter_model: str
    # 등록 모델이 temperature를 받을 때만 True다. 지원을 모르는 모델에 보내면
    # require_parameters 때문에 처리할 업체가 없어 호출이 실패할 수 있다.
    supports_temperature: bool


async def find_call_context(
    session: AsyncSession, openrouter_model: str
) -> AssistantCallContext:
    row = (
        await session.execute(
            select(Project.project_id, APIKey.key_id, Service.service_id)
            .join(APIKey, APIKey.project_id == Project.project_id)
            .join(Service, Service.service_code == ASSISTANT_SERVICE_CODE)
            .where(
                Project.project_code == SIMULATOR_PROJECT_CODE,
                APIKey.secret_ref == SIMULATOR_KEY_SECRET_REF,
                APIKey.status == KeyStatus.ACTIVE,
            )
        )
    ).one_or_none()
    if row is None:
        raise AssistantContextMissingError
    model = await session.scalar(
        select(ModelRegistry).where(
            ModelRegistry.openrouter_model_id == openrouter_model
        )
    )
    return AssistantCallContext(
        project_id=row.project_id,
        key_id=row.key_id,
        service_id=row.service_id,
        model_id=model.model_id if model else None,
        openrouter_model=openrouter_model,
        # 시뮬레이터와 같은 판단(parameter_support)을 쓴다.
        supports_temperature=bool(
            model
            and parameter_support(
                model.supported_parameters, model.openrouter_metadata
            ).temperature
        ),
    )


@dataclass(frozen=True)
class _PendingCall:
    """requests.create_pending이 기대하는 모양(PendingRequest)의 도우미 호출."""

    request_id: uuid.UUID
    project_id: int
    key_id: int
    service_id: int
    model_id: int | None
    requested_model: str
    routing_policy: Mapping[str, JsonValue]
    execution_config: Mapping[str, JsonValue]
    input_hash: str
    requested_at: datetime
    simulation_id: None = None
    executed_by: None = None
    usage_origin: UsageOrigin = UsageOrigin.ASSISTANT
    call_purpose: CallPurpose = CallPurpose.OTHER
    attempt_no: int = 1
    requested_provider: str = AUTO_PROVIDER
    data_source: DataSource = DataSource.LIVE


@dataclass(frozen=True)
class _FinishedCall:
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


def input_hash(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    """같은 입력인지 비교할 수 있게 원문 대신 해시만 남긴다."""
    text = json.dumps(
        {"messages": messages, "tools": tools}, ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(text.encode()).hexdigest()


async def start_call(
    session: AsyncSession,
    context: AssistantCallContext,
    *,
    request_id: uuid.UUID,
    routing_policy: Mapping[str, JsonValue],
    execution_config: Mapping[str, JsonValue],
    hashed_input: str,
    now: datetime,
) -> None:
    await requests.create_pending(
        session,
        _PendingCall(
            request_id=request_id,
            project_id=context.project_id,
            key_id=context.key_id,
            service_id=context.service_id,
            model_id=context.model_id,
            requested_model=context.openrouter_model,
            routing_policy=routing_policy,
            execution_config=execution_config,
            input_hash=hashed_input,
            requested_at=now,
        ),
    )
    await requests.mark_running(session, request_id, now)
    await session.commit()


async def finish_call(
    session: AsyncSession, request_id: uuid.UUID, result: CallResult, now: datetime
) -> None:
    """요청 시각과 같은 시계로 종료 시각을 남겨 시간 순서가 뒤집히지 않게 한다."""
    record = _FinishedCall(
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
    cost_source = CostSource(result.cost_source.value) if result.cost_source else None
    await requests.record_finished(
        session, request_id, record, now, cost_source=cost_source
    )
    await session.commit()


async def cancel_call(
    session: AsyncSession, request_id: uuid.UUID, now: datetime
) -> None:
    """요청이 도중에 끊긴 호출. 청구 여부는 알 수 없어 비용은 미확인으로 남는다."""
    await requests.cancel_request(session, request_id, now)
    await session.commit()


async def close_stale_calls(session: AsyncSession, now: datetime) -> int:
    """서버가 호출 도중 멈춰 PENDING·RUNNING으로 남은 도우미 호출을 취소로 닫는다.

    요청 제한 시간이 지나도 열려 있다면 그 호출을 기다리는 요청은 이미 없다. 닫은 건수를 돌려준다.
    """
    stale = await session.scalars(
        select(AIRequest.request_id).where(
            AIRequest.usage_origin == UsageOrigin.ASSISTANT.value,
            AIRequest.status.in_((RequestStatus.PENDING, RequestStatus.RUNNING)),
            AIRequest.requested_at <= now - STALE_AFTER,
        )
    )
    closed = 0
    for request_id in stale.all():
        if await requests.cancel_request(session, request_id, now):
            closed += 1
    await session.commit()
    return closed

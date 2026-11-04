"""기본 모델 찾기(P-03). 최근 고객 서비스 호출이 가장 많은 모델이 기본 모델이다."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, ModelRegistry, RequestStatus, UsageOrigin


@dataclass(frozen=True)
class BaseModel:
    model_id: int
    openrouter_model_id: str
    call_count: int
    avg_input_tokens: int | None
    avg_output_tokens: int | None


def _rounded(value: object) -> int | None:
    return None if value is None else round(value)  # type: ignore[call-overload]


async def find_base_model(
    session: AsyncSession, *, since: datetime
) -> BaseModel | None:
    """since 이후 성공한 고객 서비스 호출이 가장 많은 모델. 같으면 모델 번호가 작은 쪽."""
    calls = func.count()
    row = (
        await session.execute(
            select(
                AIRequest.model_id,
                ModelRegistry.openrouter_model_id,
                calls.label("call_count"),
                func.avg(AIRequest.input_tokens),
                func.avg(AIRequest.output_tokens),
            )
            .join(ModelRegistry, ModelRegistry.model_id == AIRequest.model_id)
            .where(
                AIRequest.usage_origin == UsageOrigin.CUSTOMER_SERVICE,
                AIRequest.status == RequestStatus.SUCCESS,
                AIRequest.requested_at >= since,
            )
            .group_by(AIRequest.model_id, ModelRegistry.openrouter_model_id)
            .order_by(calls.desc(), AIRequest.model_id)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    model_id, openrouter_model_id, call_count, avg_input, avg_output = row
    return BaseModel(
        model_id=model_id,
        openrouter_model_id=openrouter_model_id,
        call_count=call_count,
        avg_input_tokens=_rounded(avg_input),
        avg_output_tokens=_rounded(avg_output),
    )

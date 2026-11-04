"""새 모델 비교 알림(P-03) 요청·응답 모델."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import DiscoveryStatus, SkipReason
from app.schemas.plain_decimal import PlainDecimal

DEFAULT_DISCOVERY_LIMIT = 10
MAX_DISCOVERY_LIMIT = 50


class ModelDiscoveriesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=DEFAULT_DISCOVERY_LIMIT, ge=1, le=MAX_DISCOVERY_LIMIT)


class ModelDiscoveryRead(BaseModel):
    openrouter_model_id: str
    name: str
    discovered_at: datetime
    status: DiscoveryStatus
    skip_reason: SkipReason | None
    base_model_name: str | None
    new_cost_usd: PlainDecimal | None
    base_cost_usd: PlainDecimal | None
    new_latency_ms: int | None
    base_latency_ms: int | None
    # 기본 모델 대비 증감률(%). 음수면 새 모델이 더 싸거나 빠르다. 비교할 수 없으면 null
    cost_change_pct: PlainDecimal | None
    latency_change_pct: PlainDecimal | None
    cheaper: bool | None
    faster: bool | None


class ModelDiscoveriesResponse(BaseModel):
    items: list[ModelDiscoveryRead]

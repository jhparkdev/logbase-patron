"""generate_image가 돌려주는 결과 모양.

generate_image는 실패해도 예외를 던지지 않고 이 결과로 실패를 알린다.
상태·오류·비용 값의 뜻은 call_model의 CallResult와 같다.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.openrouter.errors import ErrorType
from app.openrouter.result import (
    CallStatus,
    CostSource,
    CostStatus,
    check_cost_matches_status,
)


class GeneratedImage(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 이미지 내용이 로그나 오류 문구에 찍히지 않게 repr에서 뺀다.
    data: bytes = Field(repr=False)
    media_type: str | None = None


class ImageCallResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CallStatus
    error_type: ErrorType | None = None
    error_message: str | None = None
    http_status: int | None = None
    failed_routing_step: str | None = None

    images: tuple[GeneratedImage, ...] = ()

    requested_model: str
    generation_id: str | None = None

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    image_tokens: int | None = None

    cost_usd: Decimal | None = None
    cost_status: CostStatus = CostStatus.UNKNOWN
    cost_source: CostSource | None = None

    # 이미지 내용(b64_json)은 뺀 응답 원문이다. 그대로 DB에 남겨도 되는 크기로 만든다.
    raw_response: dict[str, Any] | None = None

    started_at: datetime
    finished_at: datetime
    latency_ms: int

    @model_validator(mode="after")
    def check_cost_matches_status(self) -> Self:
        check_cost_matches_status(self.cost_status, self.cost_usd)
        return self

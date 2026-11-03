"""비용이 없는 조회 함수들의 결과 모양.

조회도 실패해도 예외를 던지지 않고 오류 유형이 담긴 결과를 돌려준다.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.openrouter.errors import ErrorType


@dataclass(frozen=True)
class LookupResult[T]:
    data: T | None = None
    error_type: ErrorType | None = None
    error_message: str | None = None
    http_status: int | None = None

    @property
    def ok(self) -> bool:
        return self.error_type is None


class ReasoningInfo(BaseModel):
    """모델의 추론 설정. OpenRouter /models의 reasoning 항목이다."""

    model_config = ConfigDict(frozen=True)

    # 추론이 필수인 모델. 이 모델에는 강도 none을 보내면 400이다
    mandatory: bool = False
    # 고를 수 있는 강도 이름. None이면 모든 강도, 빈 목록이면 강도를 고를 수 없는 모델이다
    supported_efforts: list[str] | None


class ModelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    # OpenRouter가 주는 사람이 읽는 이름(예: "OpenAI: GPT-4o"). 없으면 None이다.
    name: str | None = None
    # 모델 대표 가격(토큰당 USD). 실제 처리 업체의 단가와 다를 수 있다.
    pricing: dict[str, Decimal]
    input_modalities: list[str]
    output_modalities: list[str] = Field(default_factory=list)
    supported_parameters: list[str]
    context_length: int | None = None
    expiration_date: date | None = None
    # reasoning 항목이 없거나 모양이 틀리면 None이다(정보 없음)
    reasoning: ReasoningInfo | None = None


class EndpointInfo(BaseModel):
    """모델 하나를 실제로 처리하는 서버 업체 한 곳. provider_name은 provider.order에 그대로 쓴다."""

    model_config = ConfigDict(frozen=True)

    provider_name: str
    # OpenRouter가 주는 상태 값 그대로다. 정상일 때 0인 것은 보았지만 다른 값의 뜻은 확인하지 못했다.
    status: int | None = None
    # 최근 1일 가동률(%)
    uptime_last_1d: Decimal | None = None
    # 이 업체가 받는 설정 이름(OpenRouter의 supported_parameters). 읽지 못하면 빈 목록이다
    supported_parameters: list[str] = Field(default_factory=list)


class GenerationInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 404이면 False. 아직 기록이 생기기 전일 수도 있어 오류로 보지 않는다.
    found: bool
    total_cost: Decimal | None = None
    # 비용과 맞는 토큰 수. tokens_prompt 계열은 비용과 맞지 않아 쓰지 않는다.
    native_tokens_prompt: int | None = None
    native_tokens_completion: int | None = None
    provider: str | None = None
    cancelled: bool | None = None
    provider_statuses: list[int] = Field(default_factory=list)


class KeyUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    usage: Decimal | None = None
    usage_daily: Decimal | None = None
    usage_weekly: Decimal | None = None
    usage_monthly: Decimal | None = None
    limit: Decimal | None = None
    limit_remaining: Decimal | None = None


class KeyInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str | None = None
    disabled: bool | None = None
    limit: Decimal | None = None
    usage: Decimal | None = None
    workspace_id: str | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    # 서버 안에서 Key를 구분할 때만 쓴다. 출력, 직렬화, 로그에 나오지 않게 막아 둔다.
    key_hash: str | None = Field(default=None, repr=False, exclude=True)

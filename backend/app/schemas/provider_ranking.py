"""서버 업체 예상 비용 순위(P-03) 요청·응답 모델."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.plain_decimal import PlainDecimal

# 한 번에 계산해 볼 수 있는 토큰 수의 위쪽 한도. 터무니없는 값을 거르기 위한 것이다
MAX_RANKING_TOKENS = 10_000_000
DEFAULT_MIN_UPTIME = Decimal(90)


class ExcludedReason(StrEnum):
    """순위에서 뺀 이유. 한 업체에 하나만 알리며, 이 순서로 먼저 맞는 이유를 쓴다."""

    # OpenRouter가 준 상태가 정상(0)이 아님
    STATUS_NOT_OK = "STATUS_NOT_OK"
    # 최근 가동률(30분, 없으면 1일)이 기준 미만
    LOW_UPTIME = "LOW_UPTIME"
    # 입력 또는 출력 단가를 몰라 비용을 계산할 수 없음(0으로 계산하지 않는다)
    PRICE_UNKNOWN = "PRICE_UNKNOWN"


class ProviderRankingQuery(BaseModel):
    """GET .../execution-providers/ranking의 조건. 정해지지 않은 조건 이름은 거절한다."""

    model_config = ConfigDict(extra="forbid")

    # 작업 한 번의 예상 입력·출력 토큰 수. 작업마다 달라서 서버가 기본값을 정하지 않는다
    input_tokens: int = Field(ge=0, le=MAX_RANKING_TOKENS)
    output_tokens: int = Field(ge=0, le=MAX_RANKING_TOKENS)
    # 입력 중 캐시에서 읽을 것으로 보는 비율(0~1). 캐시 읽기 단가가 있는 업체에만 반영한다
    cache_hit_ratio: Decimal = Field(default=Decimal(0), ge=0, le=1)
    # 최근 30분 가동률(%)이 이 값 미만인 업체는 뺀다. 30분 값이 없으면 최근 1일 값으로 판단한다
    min_uptime: Decimal = Field(default=DEFAULT_MIN_UPTIME, ge=0, le=100)


class RankedProviderRead(BaseModel):
    execution_provider: str
    # 위 조건으로 작업 한 번을 처리할 때의 예상 총비용(USD)
    expected_cost_usd: PlainDecimal
    input_price_per_token: PlainDecimal
    output_price_per_token: PlainDecimal
    cache_read_price_per_token: PlainDecimal | None
    cache_write_price_per_token: PlainDecimal | None
    # 캐시 읽기 단가가 있는 업체인지
    supports_caching: bool


class ExcludedProviderRead(BaseModel):
    execution_provider: str
    reason: ExcludedReason


class ProviderRankingResponse(BaseModel):
    # 예상 총비용이 싼 순서. 비용이 같으면 업체 이름순이다
    items: list[RankedProviderRead]
    excluded: list[ExcludedProviderRead]

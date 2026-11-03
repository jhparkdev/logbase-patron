"""OpenRouter 모델 검색(P-03) 요청·응답 모델."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.models import DEFAULT_PAGE_SIZE, MAX_PAGE, MAX_PAGE_SIZE, SearchText
from app.schemas.plain_decimal import PlainDecimal


class OpenRouterModelSearchQuery(BaseModel):
    """GET /api/models/openrouter의 검색 조건. 정해지지 않은 조건 이름은 거절한다."""

    model_config = ConfigDict(extra="forbid")

    # 모델 ID나 이름에 들어 있는 글자. 없으면 전체
    q: SearchText | None = None
    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class OpenRouterModelRead(BaseModel):
    openrouter_model_id: str
    # OpenRouter가 이름을 주지 않으면 모델 ID. 등록할 때 표시 이름의 기본값으로 쓴다.
    name: str
    # 모델 ID의 '/' 앞부분. '/'가 없으면 null
    provider: str | None
    input_modalities: list[str]
    output_modalities: list[str]
    context_length: int | None
    # 토큰 1개당 단가(USD). 모르면 null
    input_price_per_token: PlainDecimal | None
    output_price_per_token: PlainDecimal | None
    supports_json_schema: bool
    supports_tools: bool
    # 이미 등록된 모델인지
    registered: bool


class OpenRouterModelListResponse(BaseModel):
    items: list[OpenRouterModelRead]
    page: int
    page_size: int
    total: int


DEFAULT_NEW_DAYS = 30
MAX_NEW_DAYS = 365
DEFAULT_NEW_LIMIT = 5
MAX_NEW_LIMIT = 50


class OpenRouterNewModelsQuery(BaseModel):
    """GET /api/models/openrouter/new의 조건. 정해지지 않은 조건 이름은 거절한다."""

    model_config = ConfigDict(extra="forbid")

    # 이 일수 안에 OpenRouter에 올라온 모델만 새 모델로 본다
    days: int = Field(default=DEFAULT_NEW_DAYS, ge=1, le=MAX_NEW_DAYS)
    # 돌려줄 모델 수. 조건에 맞는 전체 개수는 total로 따로 알려 준다
    limit: int = Field(default=DEFAULT_NEW_LIMIT, ge=1, le=MAX_NEW_LIMIT)


class OpenRouterNewModelRead(BaseModel):
    """아직 등록하지 않은 새 모델 한 건. 등록 여부는 항상 "아니오"라 담지 않는다."""

    openrouter_model_id: str
    name: str
    provider: str | None
    # OpenRouter에 올라온 시각
    created_at: datetime
    input_modalities: list[str]
    output_modalities: list[str]
    context_length: int | None
    # 토큰 1개당 단가(USD). 모르면 null
    input_price_per_token: PlainDecimal | None
    output_price_per_token: PlainDecimal | None


class OpenRouterNewModelsResponse(BaseModel):
    days: int
    # limit과 관계없이 조건에 맞는 전체 개수
    total: int
    items: list[OpenRouterNewModelRead]

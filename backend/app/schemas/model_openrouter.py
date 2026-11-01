"""OpenRouter 모델 검색(P-03) 요청·응답 모델."""

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

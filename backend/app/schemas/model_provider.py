"""모델 제공사 선택지(P-03) 응답 모델."""

from pydantic import BaseModel, ConfigDict


class ProviderRead(BaseModel):
    """화면의 제공사 선택 상자 한 줄. provider는 모델 목록의 provider 조건에 그대로 쓴다."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    model_count: int


class ProviderListResponse(BaseModel):
    items: list[ProviderRead]

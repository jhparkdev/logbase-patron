"""모델 관리(P-03) API 테스트들이 함께 쓰는 도구."""

from typing import Any

from app.openrouter.lookup_result import EndpointInfo, ModelInfo
from app.services.openrouter_catalog import OpenRouterUnavailableError


def info(model_id: str, **fields: Any) -> ModelInfo:
    values: dict[str, Any] = {
        "model_id": model_id,
        "pricing": {},
        "input_modalities": ["text"],
        "supported_parameters": [],
    }
    return ModelInfo(**{**values, **fields})


class FakeEndpointCatalog:
    """모델별 업체 목록 대신 정해 둔 목록을 돌려준다. error가 있으면 그 오류를 던지고, 어느 모델을 물었는지 기록한다."""

    def __init__(
        self, endpoints: list[EndpointInfo], error: Exception | None = None
    ) -> None:
        self.endpoints = endpoints
        self.error = error
        self.asked: list[str] = []

    async def get(self, openrouter_model_id: str) -> list[EndpointInfo]:
        self.asked.append(openrouter_model_id)
        if self.error is not None:
            raise self.error
        return self.endpoints


class FakeCatalog:
    """OpenRouter에서 받아 온 목록 대신 정해 둔 목록을 돌려준다. models가 None이면 받지 못한 것이다."""

    def __init__(self, models: list[ModelInfo] | None) -> None:
        self.models = models

    async def get(self) -> list[ModelInfo]:
        if self.models is None:
            raise OpenRouterUnavailableError
        return self.models

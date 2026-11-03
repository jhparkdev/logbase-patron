"""접수 때 서버 업체별 지원 설정을 업체 목록 보관본(EndpointCatalog)에서 읽는다."""

from collections.abc import Mapping, Sequence

from app.services.execution_provider_catalog import (
    EndpointCatalog,
    ModelNotOnOpenRouterError,
)
from app.services.openrouter_catalog import OpenRouterUnavailableError


class CatalogProviderParameters:
    def __init__(self, catalog: EndpointCatalog) -> None:
        self._catalog = catalog

    async def provider_parameters(
        self, openrouter_model_id: str
    ) -> Mapping[str, Sequence[str]] | None:
        """업체 이름별 설정 이름 목록. 이름이 같은 업체가 여러 줄이면 처음 것을 쓴다.

        업체 목록을 못 받아도 접수를 막지 않는다. None 을 돌려주면 접수는 모델 단위로만 판단한다.
        """
        try:
            endpoints = await self._catalog.get(openrouter_model_id)
        except OpenRouterUnavailableError, ModelNotOnOpenRouterError:
            return None
        by_provider: dict[str, Sequence[str]] = {}
        for endpoint in endpoints:
            by_provider.setdefault(
                endpoint.provider_name, endpoint.supported_parameters
            )
        return by_provider

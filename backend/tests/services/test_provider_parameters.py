from datetime import UTC, datetime

from app.openrouter.errors import ErrorType
from app.openrouter.lookup_result import EndpointInfo, LookupResult
from app.services.execution_provider_catalog import EndpointCatalog
from app.services.provider_parameters import CatalogProviderParameters

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
MODEL = "meta-llama/llama-3.3-70b-instruct"


def parameters_from(
    result: LookupResult[list[EndpointInfo]],
) -> CatalogProviderParameters:
    async def fetch(model_id: str) -> LookupResult[list[EndpointInfo]]:
        return result

    return CatalogProviderParameters(EndpointCatalog(fetch=fetch, now=lambda: NOW))


async def test_each_provider_is_mapped_to_the_settings_it_takes() -> None:
    lookup = parameters_from(
        LookupResult(
            data=[
                EndpointInfo(
                    provider_name="DeepInfra",
                    supported_parameters=["max_tokens", "temperature"],
                ),
                EndpointInfo(provider_name="SambaNova", supported_parameters=[]),
            ]
        )
    )

    assert await lookup.provider_parameters(MODEL) == {
        "DeepInfra": ["max_tokens", "temperature"],
        "SambaNova": [],
    }


async def test_providers_are_unknown_when_openrouter_cannot_be_reached() -> None:
    lookup = parameters_from(LookupResult(error_type=ErrorType.NETWORK_ERROR))

    assert await lookup.provider_parameters(MODEL) is None


async def test_providers_are_unknown_when_openrouter_does_not_know_the_model() -> None:
    lookup = parameters_from(
        LookupResult(error_type=ErrorType.UNKNOWN_ERROR, http_status=404)
    )

    assert await lookup.provider_parameters(MODEL) is None

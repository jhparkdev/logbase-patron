"""모델별 서버 업체 선택지(P-03) 경로. models 라우터에 붙어 /api/models/{model_id}/execution-providers가 된다."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.api.model_common import ModelIdPath, model_not_found
from app.api.model_deps import EndpointCatalogDep
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.openrouter.lookup_result import EndpointInfo
from app.schemas.common import ErrorResponse
from app.schemas.execution_provider import (
    ExecutionProviderListResponse,
    ExecutionProviderRead,
)
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.schemas.provider_ranking import (
    ExcludedProviderRead,
    ProviderRankingQuery,
    ProviderRankingResponse,
    RankedProviderRead,
)
from app.services import model_detail
from app.services.execution_provider_catalog import ModelNotOnOpenRouterError
from app.services.openrouter_catalog import OpenRouterUnavailableError
from app.services.provider_ranking import Workload, rank_providers

router = APIRouter(prefix="/{model_id}/execution-providers", tags=["models"])


async def _load_endpoints(
    model_id: int, catalog: EndpointCatalogDep, session: SessionDep
) -> list[EndpointInfo] | JSONResponse:
    """등록된 모델의 서버 업체 목록. 모델이 없으면 404, OpenRouter가 모르거나 받지 못하면 오류 응답이다."""
    item = await model_detail.get_model(session, model_id)
    if item is None:
        raise model_not_found()
    try:
        return await catalog.get(item.model.openrouter_model_id)
    except ModelNotOnOpenRouterError:
        return model_error_response(ModelErrorCode.OPENROUTER_MODEL_NOT_FOUND)
    except OpenRouterUnavailableError:
        return model_error_response(ModelErrorCode.EXECUTION_PROVIDERS_UNAVAILABLE)


@router.get(
    "",
    response_model=ExecutionProviderListResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse | ModelErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ModelErrorResponse},
    },
)
async def list_execution_providers(
    model_id: ModelIdPath, catalog: EndpointCatalogDep, session: SessionDep
) -> ExecutionProviderListResponse | JSONResponse:
    endpoints = await _load_endpoints(model_id, catalog, session)
    if isinstance(endpoints, JSONResponse):
        return endpoints
    return ExecutionProviderListResponse(
        items=[
            ExecutionProviderRead(
                execution_provider=endpoint.provider_name,
                status=endpoint.status,
                uptime_last_1d=endpoint.uptime_last_1d,
                supported_parameters=endpoint.supported_parameters,
            )
            for endpoint in endpoints
        ]
    )


@router.get(
    "/ranking",
    response_model=ProviderRankingResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse | ModelErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ModelErrorResponse},
    },
)
async def rank_execution_providers(
    model_id: ModelIdPath,
    query: Annotated[ProviderRankingQuery, Query()],
    catalog: EndpointCatalogDep,
    session: SessionDep,
) -> ProviderRankingResponse | JSONResponse:
    """업체를 예상 총비용이 싼 순서로 알려 준다. 상태·가동률이 나쁜 업체와 단가를 모르는 업체는 따로 알린다."""
    endpoints = await _load_endpoints(model_id, catalog, session)
    if isinstance(endpoints, JSONResponse):
        return endpoints
    result = rank_providers(
        endpoints,
        Workload(query.input_tokens, query.output_tokens, query.cache_hit_ratio),
        min_uptime=query.min_uptime,
    )
    return ProviderRankingResponse(
        items=[
            RankedProviderRead(
                execution_provider=item.name,
                expected_cost_usd=item.expected_cost_usd,
                input_price_per_token=item.input_price,
                output_price_per_token=item.output_price,
                cache_read_price_per_token=item.cache_read_price,
                cache_write_price_per_token=item.cache_write_price,
                supports_caching=item.supports_caching,
            )
            for item in result.ranked
        ],
        excluded=[
            ExcludedProviderRead(execution_provider=item.name, reason=item.reason)
            for item in result.excluded
        ],
    )

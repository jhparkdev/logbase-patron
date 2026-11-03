"""모델별 서버 업체 선택지(P-03) 경로. models 라우터에 붙어 /api/models/{model_id}/execution-providers가 된다."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.model_common import ModelIdPath, model_not_found
from app.api.model_deps import EndpointCatalogDep
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.schemas.common import ErrorResponse
from app.schemas.execution_provider import (
    ExecutionProviderListResponse,
    ExecutionProviderRead,
)
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.services import model_detail
from app.services.execution_provider_catalog import ModelNotOnOpenRouterError
from app.services.openrouter_catalog import OpenRouterUnavailableError

router = APIRouter(prefix="/{model_id}/execution-providers", tags=["models"])


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
    item = await model_detail.get_model(session, model_id)
    if item is None:
        raise model_not_found()
    try:
        endpoints = await catalog.get(item.model.openrouter_model_id)
    except ModelNotOnOpenRouterError:
        return model_error_response(ModelErrorCode.OPENROUTER_MODEL_NOT_FOUND)
    except OpenRouterUnavailableError:
        return model_error_response(ModelErrorCode.EXECUTION_PROVIDERS_UNAVAILABLE)
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

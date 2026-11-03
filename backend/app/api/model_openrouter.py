"""OpenRouter 모델 검색(P-03) 경로. models 라우터에 붙어 /api/models/openrouter가 된다."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.api.deps import NowDep
from app.api.model_deps import CatalogDep
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.openrouter.lookup_result import ModelInfo
from app.schemas.common import ErrorResponse
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.schemas.model_openrouter import (
    OpenRouterModelListResponse,
    OpenRouterModelRead,
    OpenRouterModelSearchQuery,
    OpenRouterNewModelRead,
    OpenRouterNewModelsQuery,
    OpenRouterNewModelsResponse,
)
from app.services import model_new, model_search
from app.services.model_new import NewModel
from app.services.model_registry import (
    provider_from_model_id,
    snapshot_from_pricing,
    supports_json_schema,
    supports_tools,
)
from app.services.openrouter_catalog import OpenRouterUnavailableError

router = APIRouter(prefix="/openrouter", tags=["models"])


def to_openrouter_model_read(info: ModelInfo, registered: bool) -> OpenRouterModelRead:
    price = snapshot_from_pricing(info.pricing)
    return OpenRouterModelRead(
        openrouter_model_id=info.model_id,
        name=info.name or info.model_id,
        provider=provider_from_model_id(info.model_id),
        input_modalities=info.input_modalities,
        output_modalities=info.output_modalities,
        context_length=info.context_length,
        input_price_per_token=price.input_price_per_token if price else None,
        output_price_per_token=price.output_price_per_token if price else None,
        supports_json_schema=supports_json_schema(info.supported_parameters),
        supports_tools=supports_tools(info.supported_parameters),
        registered=registered,
    )


def to_new_model_read(entry: NewModel) -> OpenRouterNewModelRead:
    info = entry.model
    price = snapshot_from_pricing(info.pricing)
    return OpenRouterNewModelRead(
        openrouter_model_id=info.model_id,
        name=info.name or info.model_id,
        provider=provider_from_model_id(info.model_id),
        created_at=entry.created_at,
        input_modalities=info.input_modalities,
        output_modalities=info.output_modalities,
        context_length=info.context_length,
        input_price_per_token=price.input_price_per_token if price else None,
        output_price_per_token=price.output_price_per_token if price else None,
    )


@router.get(
    "",
    response_model=OpenRouterModelListResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ModelErrorResponse},
    },
)
async def search_openrouter_models(
    query: Annotated[OpenRouterModelSearchQuery, Query()],
    catalog: CatalogDep,
    session: SessionDep,
) -> OpenRouterModelListResponse | JSONResponse:
    try:
        models = await catalog.get()
    except OpenRouterUnavailableError:
        return model_error_response(ModelErrorCode.OPENROUTER_UNAVAILABLE)

    page = model_search.search_models(
        models, q=query.q, page=query.page, page_size=query.page_size
    )
    registered = await model_search.find_registered(
        session, [model.model_id for model in page.items]
    )
    return OpenRouterModelListResponse(
        items=[
            to_openrouter_model_read(model, model.model_id in registered)
            for model in page.items
        ],
        page=query.page,
        page_size=query.page_size,
        total=page.total,
    )


@router.get(
    "/new",
    response_model=OpenRouterNewModelsResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ModelErrorResponse},
    },
)
async def list_new_openrouter_models(
    query: Annotated[OpenRouterNewModelsQuery, Query()],
    catalog: CatalogDep,
    session: SessionDep,
    now: NowDep,
) -> OpenRouterNewModelsResponse | JSONResponse:
    """최근에 OpenRouter에 올라왔고 아직 등록하지 않은 모델. 모델 관리 화면의 신규 모델 알림에 쓴다."""
    try:
        models = await catalog.get()
    except OpenRouterUnavailableError:
        return model_error_response(ModelErrorCode.OPENROUTER_UNAVAILABLE)

    found = await model_new.find_new_models(
        session, models, now=now, days=query.days, limit=query.limit
    )
    return OpenRouterNewModelsResponse(
        days=query.days,
        total=found.total,
        items=[to_new_model_read(entry) for entry in found.items],
    )

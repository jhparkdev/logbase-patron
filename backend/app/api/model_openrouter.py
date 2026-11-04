"""OpenRouter 모델 검색(P-03) 경로. models 라우터에 붙어 /api/models/openrouter가 된다."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.api.deps import NowDep
from app.api.model_deps import CatalogDep
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.openrouter.lookup_result import ModelInfo
from app.schemas.common import ErrorResponse
from app.schemas.model_discovery import (
    ModelDiscoveriesQuery,
    ModelDiscoveriesResponse,
    ModelDiscoveryRead,
)
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.schemas.model_openrouter import (
    OpenRouterModelListResponse,
    OpenRouterModelRead,
    OpenRouterModelSearchQuery,
    OpenRouterNewModelRead,
    OpenRouterNewModelsQuery,
    OpenRouterNewModelsResponse,
)
from app.services import model_discovery_list, model_new, model_search
from app.services.model_comparison import CallMetrics, compare
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
        created_at=info.created_at,
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
    now: NowDep,
) -> OpenRouterModelListResponse | JSONResponse:
    try:
        models = await catalog.get()
    except OpenRouterUnavailableError:
        return model_error_response(ModelErrorCode.OPENROUTER_UNAVAILABLE)

    if query.new_days is not None:
        found = await model_new.search_new_models(
            session,
            models,
            q=query.q,
            now=now,
            days=query.new_days,
            page=query.page,
            page_size=query.page_size,
        )
        # 새 모델은 미등록만 골라 오므로 등록 여부는 항상 아니오다
        return OpenRouterModelListResponse(
            items=[
                to_openrouter_model_read(entry.model, False) for entry in found.items
            ],
            page=query.page,
            page_size=query.page_size,
            total=found.total,
        )

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


PCT_PLACES = Decimal("0.1")


def to_discovery_read(row: model_discovery_list.DiscoveryRow) -> ModelDiscoveryRead:
    found = row.discovery
    comparison = compare(
        CallMetrics(found.base_cost_usd, found.base_latency_ms),
        CallMetrics(found.new_cost_usd, found.new_latency_ms),
    )
    return ModelDiscoveryRead(
        openrouter_model_id=found.openrouter_model_id,
        name=found.model_name or found.openrouter_model_id,
        discovered_at=found.discovered_at,
        status=found.status,
        skip_reason=found.skip_reason,
        base_model_name=row.base_model_name,
        new_cost_usd=found.new_cost_usd,
        base_cost_usd=found.base_cost_usd,
        new_latency_ms=found.new_latency_ms,
        base_latency_ms=found.base_latency_ms,
        cost_change_pct=_rounded(comparison.cost_change_pct),
        latency_change_pct=_rounded(comparison.latency_change_pct),
        cheaper=comparison.cheaper,
        faster=comparison.faster,
    )


def _rounded(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(PCT_PLACES)


@router.get(
    "/discoveries",
    response_model=ModelDiscoveriesResponse,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}},
)
async def list_model_discoveries(
    query: Annotated[ModelDiscoveriesQuery, Query()], session: SessionDep
) -> ModelDiscoveriesResponse:
    """새 모델과 기본 모델의 비교 결과. 모델 관리 화면의 신규 모델 알림에 쓴다."""
    rows = await model_discovery_list.list_discoveries(session, limit=query.limit)
    return ModelDiscoveriesResponse(items=[to_discovery_read(row) for row in rows])

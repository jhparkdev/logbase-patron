"""모델 관리(P-03) 경로. 입력 검증과 응답 변환만 하고, 조회는 services가 한다."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import JSONResponse

from app.api import model_openrouter
from app.api.deps import DevUserDep, NowDep
from app.api.errors import ApiError
from app.api.model_deps import CatalogDep
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.schemas.model_provider import ProviderListResponse, ProviderRead
from app.schemas.model_register import ModelCreate
from app.schemas.models import (
    MAX_MODEL_ID,
    ModelDetailRead,
    ModelListQuery,
    ModelListResponse,
    ModelRead,
    PriceRead,
    SortOrder,
)
from app.services import model_detail, model_list, model_providers, model_register
from app.services.model_list import ModelListItem
from app.services.model_register import (
    ModelAlreadyRegisteredError,
    ModelNotInOpenRouterError,
)
from app.services.model_registry import supports_json_schema, supports_tools
from app.services.openrouter_catalog import OpenRouterUnavailableError

ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
DETAIL_ERROR_RESPONSES = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
CREATE_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ModelErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse | ModelErrorResponse,
    },
    status.HTTP_502_BAD_GATEWAY: {"model": ModelErrorResponse},
}
MODEL_NOT_FOUND_MESSAGE = "모델을 찾을 수 없습니다."

router = APIRouter(prefix="/models", tags=["models"])


def to_model_read(item: ModelListItem) -> ModelRead:
    model = item.model
    return ModelRead(
        model_id=model.model_id,
        openrouter_model_id=model.openrouter_model_id,
        display_name=model.display_name,
        provider=model.provider,
        purpose=model.purpose,
        status=model.status,
        input_modalities=model.input_modalities,
        output_modalities=model.output_modalities,
        supports_json_schema=supports_json_schema(model.supported_parameters),
        supports_tools=supports_tools(model.supported_parameters),
        context_length=model.context_length,
        current_price=(
            PriceRead.model_validate(item.price) if item.price is not None else None
        ),
        last_test_status=model.last_test_status,
        last_test_at=model.last_test_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def to_model_detail_read(item: ModelListItem) -> ModelDetailRead:
    model = item.model
    return ModelDetailRead(
        **to_model_read(item).model_dump(),
        activated_at=model.activated_at,
        deactivated_at=model.deactivated_at,
        last_success_test_at=model.last_success_test_at,
    )


@router.get("", responses=ERROR_RESPONSES)
async def list_models(
    query: Annotated[ModelListQuery, Query()], session: SessionDep
) -> ModelListResponse:
    page = await model_list.list_models(
        session,
        q=query.q,
        name=query.name,
        model_id=query.model_id,
        provider=query.provider,
        statuses=[model_status.value for model_status in query.status],
        sort=query.sort.value,
        descending=query.order == SortOrder.DESC,
        page=query.page,
        page_size=query.page_size,
    )
    return ModelListResponse(
        items=[to_model_read(item) for item in page.items],
        page=query.page,
        page_size=query.page_size,
        total=page.total,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ModelDetailRead,
    responses=CREATE_ERROR_RESPONSES,
)
async def register_model(
    body: ModelCreate,
    catalog: CatalogDep,
    session: SessionDep,
    user: DevUserDep,
    now: NowDep,
) -> ModelDetailRead | JSONResponse:
    try:
        models = await catalog.get()
        model_id = await model_register.register_model(
            session,
            models,
            openrouter_model_id=body.openrouter_model_id,
            display_name=body.display_name,
            purpose=body.purpose,
            user_id=user.user_id,
            now=now,
        )
    except OpenRouterUnavailableError:
        return model_error_response(ModelErrorCode.OPENROUTER_UNAVAILABLE)
    except ModelNotInOpenRouterError:
        return model_error_response(ModelErrorCode.MODEL_NOT_IN_OPENROUTER)
    except ModelAlreadyRegisteredError:
        return model_error_response(ModelErrorCode.MODEL_ALREADY_REGISTERED)
    item = await model_detail.get_model(session, model_id)
    if item is None:
        raise RuntimeError("방금 등록한 모델을 찾지 못했다")
    return to_model_detail_read(item)


# "/{model_id}"보다 먼저 선언해야 "providers"가 모델 번호로 해석되지 않는다.
@router.get("/providers")
async def list_model_providers(session: SessionDep) -> ProviderListResponse:
    providers = await model_providers.list_providers(session)
    return ProviderListResponse(
        items=[ProviderRead.model_validate(item) for item in providers]
    )


router.include_router(model_openrouter.router)


@router.get("/{model_id}", responses=DETAIL_ERROR_RESPONSES)
async def read_model(
    model_id: Annotated[int, Path(ge=1, le=MAX_MODEL_ID)], session: SessionDep
) -> ModelDetailRead:
    item = await model_detail.get_model(session, model_id)
    if item is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, MODEL_NOT_FOUND_MESSAGE
        )
    return to_model_detail_read(item)

"""모델 관리(P-03) 경로. 입력 검증과 응답 변환만 하고, 조회는 services가 한다."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.api import model_execution_providers, model_manage, model_openrouter
from app.api.deps import CurrentUserDep, NowDep
from app.api.model_common import (
    ModelIdPath,
    model_not_found,
    to_model_detail_read,
    to_model_read,
)
from app.api.model_deps import CatalogDep
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.schemas.common import ErrorResponse
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.schemas.model_provider import ProviderListResponse, ProviderRead
from app.schemas.model_register import ModelCreate
from app.schemas.models import (
    ModelDetailRead,
    ModelListQuery,
    ModelListResponse,
    SortOrder,
)
from app.services import model_detail, model_list, model_providers, model_register
from app.services.model_register import (
    ModelAlreadyRegisteredError,
    ModelNotInOpenRouterError,
)
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

router = APIRouter(prefix="/models", tags=["models"])


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
    user: CurrentUserDep,
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
router.include_router(model_execution_providers.router)
router.include_router(model_manage.router)


@router.get("/{model_id}", responses=DETAIL_ERROR_RESPONSES)
async def read_model(model_id: ModelIdPath, session: SessionDep) -> ModelDetailRead:
    item = await model_detail.get_model(session, model_id)
    if item is None:
        raise model_not_found()
    return to_model_detail_read(item)

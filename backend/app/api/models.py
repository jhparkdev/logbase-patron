"""모델 관리(P-03) 경로. 입력 검증과 응답 변환만 하고, 조회는 services가 한다."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.errors import ApiError
from app.db import SessionDep
from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.models import (
    MAX_MODEL_ID,
    ModelDetailRead,
    ModelListQuery,
    ModelListResponse,
    ModelRead,
    PriceRead,
    SortOrder,
)
from app.services import model_detail, model_list
from app.services.model_list import ModelListItem
from app.services.model_registry import supports_json_schema

ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
DETAIL_ERROR_RESPONSES = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
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

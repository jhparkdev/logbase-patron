"""모델 관리(P-03) 경로들이 함께 쓰는 입력 형식과 응답 변환."""

from typing import Annotated

from fastapi import Path, status

from app.api.errors import ApiError
from app.schemas.common import ErrorCode
from app.schemas.models import MAX_MODEL_ID, ModelDetailRead, ModelRead, PriceRead
from app.services.model_list import ModelListItem
from app.services.model_parameters import parameter_support
from app.services.model_registry import (
    stored_reasoning_efforts,
    supports_json_schema,
    supports_tools,
)

MODEL_NOT_FOUND_MESSAGE = "모델을 찾을 수 없습니다."

ModelIdPath = Annotated[int, Path(ge=1, le=MAX_MODEL_ID)]


def model_not_found() -> ApiError:
    return ApiError(
        status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, MODEL_NOT_FOUND_MESSAGE
    )


def to_model_read(item: ModelListItem) -> ModelRead:
    model = item.model
    support = parameter_support(model.supported_parameters)
    stored = stored_reasoning_efforts(model.openrouter_metadata)
    # 추론을 받는 모델에서만, 등록할 때 저장한 강도 목록이 있으면 그것을 쓴다
    efforts = (
        stored
        if support.reasoning_efforts and stored is not None
        else support.reasoning_efforts
    )
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
        temperature_supported=support.temperature,
        reasoning_efforts=list(efforts),
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

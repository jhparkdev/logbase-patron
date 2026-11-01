"""모델 수정·상태 변경(P-03) 경로. models 라우터에 붙어 /api/models/{model_id}...가 된다."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DevUserDep, NowDep
from app.api.model_common import ModelIdPath, model_not_found, to_model_detail_read
from app.api.model_errors import model_error_response
from app.db import SessionDep
from app.schemas.common import ErrorResponse
from app.schemas.model_error import ModelErrorCode, ModelErrorResponse
from app.schemas.model_update import ModelStatusChange, ModelUpdate
from app.schemas.models import ModelDetailRead
from app.services import model_detail, model_update
from app.services.model_update import ModelNotFoundError, StatusChangeRefusedError

COMMON_ERROR_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
STATUS_ERROR_RESPONSES = {
    **COMMON_ERROR_RESPONSES,
    status.HTTP_409_CONFLICT: {"model": ModelErrorResponse},
}

router = APIRouter(prefix="/{model_id}", tags=["models"])


async def _read_detail(session: AsyncSession, model_id: int) -> ModelDetailRead:
    item = await model_detail.get_model(session, model_id)
    if item is None:
        raise model_not_found()
    return to_model_detail_read(item)


@router.patch("", response_model=ModelDetailRead, responses=COMMON_ERROR_RESPONSES)
async def update_model_info(
    model_id: ModelIdPath, body: ModelUpdate, session: SessionDep, user: DevUserDep
) -> ModelDetailRead:
    try:
        # 보낸 항목만 넘긴다. 보내지 않은 항목은 바뀌지 않는다.
        await model_update.update_model(
            session, model_id, body.model_dump(exclude_unset=True), user.user_id
        )
    except ModelNotFoundError as error:
        raise model_not_found() from error
    return await _read_detail(session, model_id)


@router.patch(
    "/status", response_model=ModelDetailRead, responses=STATUS_ERROR_RESPONSES
)
async def change_model_status(
    model_id: ModelIdPath,
    body: ModelStatusChange,
    session: SessionDep,
    user: DevUserDep,
    now: NowDep,
) -> ModelDetailRead | JSONResponse:
    try:
        await model_update.change_status(
            session, model_id, body.status, user.user_id, now
        )
    except ModelNotFoundError as error:
        raise model_not_found() from error
    except StatusChangeRefusedError as error:
        return model_error_response(ModelErrorCode(error.reason.value))
    return await _read_detail(session, model_id)

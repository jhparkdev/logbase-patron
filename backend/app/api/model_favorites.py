"""모델+Provider 즐겨찾기 라우터. 로그인한 계정의 것만 다룬다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUserDep, get_current_user
from app.api.errors import VALIDATION_MESSAGE, ApiError
from app.db import SessionDep
from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.model_favorite import (
    ModelFavoriteKey,
    ModelFavoriteList,
    ModelFavoriteRead,
)
from app.services import model_favorites
from app.services.model_favorites import FavoriteModelNotFoundError

# main.py 는 라우터 단위 로그인 검사를 하지 않으므로, 시뮬레이터 라우터와 같게 여기서 세션을 요구한다.
router = APIRouter(
    prefix="/model-favorites",
    tags=["model-favorites"],
    dependencies=[Depends(get_current_user)],
)


# 받는 값은 없지만 세션 쿠키를 읽으므로 FastAPI 가 422 를 문서에 넣는다. 실제 형식({code, message})으로 적는다
@router.get(
    "",
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}},
)
async def list_model_favorites(
    user: CurrentUserDep, session: SessionDep
) -> ModelFavoriteList:
    rows = await model_favorites.list_favorites(session, user.user_id)
    return ModelFavoriteList(items=[ModelFavoriteRead.model_validate(r) for r in rows])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"model": ModelFavoriteRead},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def add_model_favorite(
    body: ModelFavoriteKey,
    response: Response,
    user: CurrentUserDep,
    session: SessionDep,
) -> ModelFavoriteRead:
    """등록한다. 이미 있으면 200 으로 같은 항목을 돌려줘 화면이 두 번 눌러도 안전하다."""
    try:
        row, created = await model_favorites.add_favorite(
            session, user.user_id, body.model_id, body.execution_provider
        )
    except FavoriteModelNotFoundError as error:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.VALIDATION_ERROR,
            VALIDATION_MESSAGE,
        ) from error
    await session.commit()
    if not created:
        response.status_code = status.HTTP_200_OK
    return ModelFavoriteRead.model_validate(row)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def remove_model_favorite(
    key: Annotated[ModelFavoriteKey, Query()],
    user: CurrentUserDep,
    session: SessionDep,
) -> Response:
    """해제한다. 없는 항목도 204 다. 삭제와 목록은 그 계정의 행에만 닿는다."""
    await model_favorites.remove_favorite(
        session, user.user_id, key.model_id, key.execution_provider
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

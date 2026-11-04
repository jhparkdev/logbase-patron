"""월 구독료(P-02) 경로. 입력 검증과 응답 변환만 하고, 규칙은 services/subscriptions가 한다.

로그인 검사는 팀 결정으로 뒤로 미뤘다(main.py). 복구할 때 이 라우터도 함께 대상이 된다.
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import JSONResponse

from app.api.deps import DevUserDep, NowDep
from app.api.errors import ApiError
from app.api.internal_budget import period_of
from app.api.usage import DETAIL_ERRORS, QUERY_ERRORS
from app.db import SessionDep
from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.models import MAX_MODEL_ID
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionList,
    SubscriptionOptions,
    SubscriptionRow,
    SubscriptionsQuery,
    SubscriptionUpdate,
)
from app.schemas.subscription_error import (
    DUPLICATE_MESSAGE,
    SubscriptionErrorCode,
    SubscriptionErrorResponse,
)
from app.services import subscriptions
from app.services.simulation_period import kst_today
from app.services.subscriptions import (
    SubscriptionDuplicateError,
    SubscriptionNotFoundError,
    SubscriptionProjectNotFoundError,
)

SUBSCRIPTION_NOT_FOUND_MESSAGE = "구독료를 찾을 수 없어요."
PROJECT_NOT_FOUND_MESSAGE = "선택한 프로젝트를 찾을 수 없어요."
CREATE_ERRORS = {
    status.HTTP_409_CONFLICT: {"model": SubscriptionErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
SubscriptionIdPath = Annotated[int, Path(ge=1, le=MAX_MODEL_ID)]

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _project_not_found() -> ApiError:
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        PROJECT_NOT_FOUND_MESSAGE,
    )


@router.get("", responses=QUERY_ERRORS)
async def read_subscriptions(
    query: Annotated[SubscriptionsQuery, Query()], session: SessionDep, now: NowDep
) -> SubscriptionList:
    period = period_of(query, kst_today(now))
    return await subscriptions.list_subscriptions(session, period, query)


@router.get("/options")
async def read_options(session: SessionDep) -> SubscriptionOptions:
    return SubscriptionOptions(
        projects=await subscriptions.list_project_options(session)
    )


@router.get("/{subscription_id}", responses=DETAIL_ERRORS)
async def read_subscription(
    subscription_id: SubscriptionIdPath, session: SessionDep
) -> SubscriptionRow:
    row = await subscriptions.get_subscription(session, subscription_id)
    if row is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.NOT_FOUND,
            SUBSCRIPTION_NOT_FOUND_MESSAGE,
        )
    return row


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SubscriptionRow,
    responses=CREATE_ERRORS,
)
async def create_subscription(
    body: SubscriptionCreate, session: SessionDep, user: DevUserDep
) -> SubscriptionRow | JSONResponse:
    try:
        # dict(body)는 값을 그대로 꺼낸다. model_dump()는 Month를 "YYYY-MM" 문자열로 바꾼다
        return await subscriptions.create_subscription(
            session, dict(body), user.user_id
        )
    except SubscriptionDuplicateError:
        error_body = SubscriptionErrorResponse(
            code=SubscriptionErrorCode.SUBSCRIPTION_DUPLICATE,
            message=DUPLICATE_MESSAGE,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_body.model_dump(mode="json"),
        )
    except SubscriptionProjectNotFoundError as error:
        raise _project_not_found() from error


@router.patch("/{subscription_id}", responses=DETAIL_ERRORS)
async def update_subscription(
    subscription_id: SubscriptionIdPath,
    body: SubscriptionUpdate,
    session: SessionDep,
    user: DevUserDep,
) -> SubscriptionRow:
    try:
        return await subscriptions.update_subscription(
            session,
            subscription_id,
            body.model_dump(exclude_unset=True),
            user.user_id,
        )
    except SubscriptionNotFoundError as error:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            ErrorCode.NOT_FOUND,
            SUBSCRIPTION_NOT_FOUND_MESSAGE,
        ) from error
    except SubscriptionProjectNotFoundError as error:
        raise _project_not_found() from error

"""인증된 AI 도우미 API. 기존 기능 API의 인증 정책은 변경하지 않는다."""

import asyncio

from fastapi import APIRouter

from app.api.assistant_deps import (
    CallerDep,
    active_model,
    assistant_capacity,
    cleanup_lifespan,
    unavailable_message,
    uses_openrouter,
)
from app.api.assistant_gate import AssistantGate
from app.api.deps import CurrentUserDep, NowDep, SettingsDep
from app.api.errors import ApiError
from app.api.model_deps import EndpointCatalogDep
from app.db import SessionDep
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantSettingsRequest,
    AssistantStatus,
    SimulatorPatch,
)
from app.schemas.common import ErrorCode, ErrorResponse
from app.services.assistant import answer
from app.services.assistant_budget import daily_limit_reached, spent_today
from app.services.assistant_reply import (
    AssistantReplyTruncatedError,
    AssistantUnavailableError,
)
from app.services.assistant_settings import InvalidSettingsError, validate_patch
from app.services.assistant_tools import AssistantTools
from app.services.execution_provider_catalog import ModelNotOnOpenRouterError
from app.services.openrouter_catalog import OpenRouterUnavailableError

router = APIRouter(prefix="/assistant", tags=["assistant"], lifespan=cleanup_lifespan)
_gate = AssistantGate()
REQUEST_TIMEOUT_SECONDS = 120
ERRORS = {code: {"model": ErrorResponse} for code in (401, 422, 429, 502, 503)}


@router.get("/status", responses=ERRORS)
async def read_status(_: CurrentUserDep, settings: SettingsDep) -> AssistantStatus:
    return AssistantStatus(
        enabled=settings.assistant_enabled, model=active_model(settings)
    )


@router.post("/chat", responses=ERRORS, response_model_exclude_unset=True)
async def chat(
    request: AssistantChatRequest,
    user: CurrentUserDep,
    session: SessionDep,
    catalog: EndpointCatalogDep,
    now: NowDep,
    settings: SettingsDep,
    caller: CallerDep,
) -> AssistantChatResponse:
    if uses_openrouter(settings) and daily_limit_reached(
        await spent_today(session, now), settings.assistant_daily_limit_usd
    ):
        raise ApiError(
            429,
            ErrorCode.BAD_REQUEST,
            "오늘 AI 도우미 사용 한도에 도달했어요. 내일 다시 이용하거나 관리자에게 문의해 주세요.",
        )
    if not _gate.try_enter(user_id=user.user_id, capacity=assistant_capacity(settings)):
        raise ApiError(
            429,
            ErrorCode.BAD_REQUEST,
            "AI가 다른 요청을 처리하고 있어요. 이전 답변을 받은 뒤 다시 시도해 주세요.",
        )
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            return await answer(
                request,
                caller,
                AssistantTools(
                    session,
                    catalog,
                    now,
                    request.simulator,
                    request.page_context,
                    request.messages[-1].content,
                    tuple(
                        message.content
                        for message in request.messages[:-1]
                        if message.role == "user"
                    ),
                ),
                now=now,
            )
    except AssistantReplyTruncatedError:
        raise ApiError(
            503,
            ErrorCode.BAD_REQUEST,
            "요청이 길어 답을 끝까지 만들지 못했어요. 바꿀 항목을 두 번에 나눠 요청해 주세요.",
        ) from None
    except AssistantUnavailableError, TimeoutError:
        raise ApiError(
            503, ErrorCode.BAD_REQUEST, unavailable_message(settings)
        ) from None
    finally:
        _gate.leave(user_id=user.user_id)


@router.post("/settings/validate", responses=ERRORS, response_model_exclude_unset=True)
async def validate_settings(
    request: AssistantSettingsRequest,
    _: CurrentUserDep,
    settings: SettingsDep,
    session: SessionDep,
    catalog: EndpointCatalogDep,
) -> SimulatorPatch:
    if not settings.assistant_enabled:
        raise ApiError(503, ErrorCode.BAD_REQUEST, "AI 도우미가 비활성화되어 있어요.")
    try:
        return await validate_patch(session, catalog, request.simulator, request.patch)
    except InvalidSettingsError as error:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, str(error)) from None
    except OpenRouterUnavailableError, ModelNotOnOpenRouterError:
        raise ApiError(
            502,
            ErrorCode.BAD_REQUEST,
            "서버 업체 정보를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from None

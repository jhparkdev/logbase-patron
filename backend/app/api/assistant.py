"""인증된 로컬 보조 AI API. 기존 기능 API의 인증 정책은 변경하지 않는다."""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends

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
from app.services.assistant_ollama import AssistantUnavailableError, OllamaCaller
from app.services.assistant_settings import InvalidSettingsError, validate_patch
from app.services.assistant_tools import AssistantTools
from app.services.execution_provider_catalog import ModelNotOnOpenRouterError
from app.services.openrouter_catalog import OpenRouterUnavailableError

router = APIRouter(prefix="/assistant", tags=["assistant"])
_gate = asyncio.Semaphore(1)
ERRORS = {code: {"model": ErrorResponse} for code in (401, 422, 429, 502, 503)}


async def get_assistant_caller(settings: SettingsDep) -> AsyncIterator[OllamaCaller]:
    if not settings.assistant_enabled:
        raise ApiError(
            503,
            ErrorCode.BAD_REQUEST,
            "AI 도우미가 비활성화되어 있어요. 관리자에게 문의해 주세요.",
        )
    # 서버 설정만 목적지로 사용한다. 사용자·모델이 보낸 URL은 받지 않으며 프록시·리다이렉트를 쓰지 않는다.
    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url,
        timeout=90,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        yield OllamaCaller(
            client, settings.ollama_model, settings.ollama_context_length
        )


CallerDep = Annotated[OllamaCaller, Depends(get_assistant_caller)]


@router.get("/status", responses=ERRORS)
async def read_status(_: CurrentUserDep, settings: SettingsDep) -> AssistantStatus:
    return AssistantStatus(
        enabled=settings.assistant_enabled, model=settings.ollama_model
    )


@router.post("/chat", responses=ERRORS, response_model_exclude_unset=True)
async def chat(
    request: AssistantChatRequest,
    _: CurrentUserDep,
    session: SessionDep,
    catalog: EndpointCatalogDep,
    now: NowDep,
    caller: CallerDep,
) -> AssistantChatResponse:
    try:
        await asyncio.wait_for(_gate.acquire(), timeout=0.1)
    except TimeoutError:
        raise ApiError(
            429,
            ErrorCode.BAD_REQUEST,
            "AI가 다른 요청을 처리하고 있어요. 잠시 후 다시 시도해 주세요.",
        ) from None
    try:
        async with asyncio.timeout(120):
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
    except AssistantUnavailableError, TimeoutError:
        raise ApiError(
            503,
            ErrorCode.BAD_REQUEST,
            "로컬 AI의 응답을 받지 못했어요. Ollama와 모델 실행 상태를 확인한 뒤 다시 시도해 주세요.",
        ) from None
    finally:
        _gate.release()


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
        await validate_patch(session, catalog, request.simulator, request.patch)
    except InvalidSettingsError as error:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, str(error)) from None
    except OpenRouterUnavailableError, ModelNotOnOpenRouterError:
        raise ApiError(
            502,
            ErrorCode.BAD_REQUEST,
            "서버 업체 정보를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from None
    return request.patch

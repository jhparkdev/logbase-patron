"""AI 도우미 라우터의 의존성. 설정한 모델 서비스(Ollama·OpenRouter)에 맞는 호출부를 만든다."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI
from pydantic import SecretStr
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SettingsDep
from app.api.errors import ApiError
from app.config import Settings
from app.db import SessionDep, get_sessionmaker
from app.openrouter.client import OpenRouterClient
from app.schemas.common import ErrorCode
from app.services.assistant import ChatCaller
from app.services.assistant_ollama import OllamaCaller
from app.services.assistant_openrouter import ModelCall, OpenRouterAssistantCaller
from app.services.assistant_records import (
    AssistantContextMissingError,
    close_stale_calls,
    find_call_context,
)

# 로그에는 건수와 예외 종류만 남긴다. 예외 메시지에 접속 정보가 들어갈 수 있다.
logger = logging.getLogger(__name__)

# 로컬 GPU를 보호하려고 한 번에 한 요청만 받는다.
OLLAMA_CAPACITY = 1
# 외부 과금 호출이라 동시에 처리하는 요청 수를 작게 둔다.
OPENROUTER_CAPACITY = 3
OLLAMA_TIMEOUT_SECONDS = 90


def _unavailable(message: str) -> ApiError:
    return ApiError(503, ErrorCode.BAD_REQUEST, message)


def uses_openrouter(settings: Settings) -> bool:
    return settings.assistant_provider == "openrouter"


def assistant_capacity(settings: Settings) -> int:
    return OPENROUTER_CAPACITY if uses_openrouter(settings) else OLLAMA_CAPACITY


def active_model(settings: Settings) -> str:
    if uses_openrouter(settings):
        return settings.assistant_model or ""
    return settings.ollama_model


def unavailable_message(settings: Settings) -> str:
    if uses_openrouter(settings):
        return "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요."
    return "로컬 AI의 응답을 받지 못했어요. Ollama와 모델 실행 상태를 확인한 뒤 다시 시도해 주세요."


@lru_cache
def _openrouter_client(api_key: SecretStr) -> OpenRouterClient:
    """앱 수명 동안 하나만 만들어 연결을 재사용한다."""
    return OpenRouterClient(
        http_client=httpx.AsyncClient(), api_key=api_key.get_secret_value()
    )


def get_assistant_model_call(settings: SettingsDep) -> ModelCall | None:
    """OpenRouter 모델 호출 함수. 테스트는 가짜 호출 함수로 바꿔 끼운다."""
    api_key = settings.openrouter_api_key
    if not uses_openrouter(settings) or api_key is None:
        return None
    # 값만 지운 줄(OPENROUTER_API_KEY=)은 빈 문자열로 읽히므로 없는 것과 같이 본다
    if not api_key.get_secret_value():
        return None
    return _openrouter_client(api_key).call_model


ModelCallDep = Annotated[ModelCall | None, Depends(get_assistant_model_call)]


async def get_assistant_caller(
    settings: SettingsDep, session: SessionDep, model_call: ModelCallDep
) -> AsyncIterator[ChatCaller]:
    if not settings.assistant_enabled:
        raise _unavailable("AI 도우미가 비활성화되어 있어요. 관리자에게 문의해 주세요.")
    if uses_openrouter(settings):
        if model_call is None:
            raise _unavailable(
                "OpenRouter Key가 설정되지 않아 AI 도우미를 사용할 수 없어요. 관리자에게 문의해 주세요."
            )
        try:
            context = await find_call_context(session, active_model(settings))
        except AssistantContextMissingError:
            raise _unavailable(
                "AI 도우미 비용을 기록할 대상이 준비되지 않았어요. 관리자에게 문의해 주세요."
            ) from None
        yield OpenRouterAssistantCaller(
            model_call, session, context, clock=lambda: datetime.now(UTC)
        )
        return
    # 서버 설정만 목적지로 사용한다. 사용자·모델이 보낸 URL은 받지 않으며 프록시·리다이렉트를 쓰지 않는다.
    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url,
        timeout=OLLAMA_TIMEOUT_SECONDS,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        yield OllamaCaller(
            client, settings.ollama_model, settings.ollama_context_length
        )


CallerDep = Annotated[ChatCaller, Depends(get_assistant_caller)]


@asynccontextmanager
async def cleanup_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버가 시작할 때 이전 프로세스가 호출 도중 남긴 도우미 이력을 한 번 닫는다.

    도우미 라우터의 lifespan이다. 테스트 클라이언트(ASGITransport)는 lifespan을 돌리지 않는다.
    DB에 닿지 못해도 서버는 띄우고, 다음 시작 때 다시 정리한다.
    """
    try:
        async with get_sessionmaker()() as session:
            closed = await close_stale_calls(session, datetime.now(UTC))
        if closed:
            logger.info("assistant cleanup: closed_calls=%s", closed)
    except SQLAlchemyError as error:
        logger.error("assistant cleanup failed: error=%s", type(error).__name__)
    yield

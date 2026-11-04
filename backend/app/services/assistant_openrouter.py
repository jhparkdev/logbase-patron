"""OpenRouter로 도우미 모델을 부르는 호출부. 호출마다 호출 이력을 남긴다.

OpenRouter 호출은 openrouter/client.py의 call_model로만 한다. 프롬프트와 응답은 로깅하지 않는다.
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from pydantic import JsonValue, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.openrouter.result import CallResult, CallStatus
from app.services.assistant_records import (
    AssistantCallContext,
    cancel_call,
    finish_call,
    input_hash,
    start_call,
)
from app.services.assistant_reply import (
    AssistantReply,
    AssistantReplyTruncatedError,
    AssistantUnavailableError,
    ToolCall,
)

# 여러 칸을 한 번에 바꾸는 설정 도구 호출(Prompt·입력 텍스트·모델 목록)이 768에서 잘린 사례가 있어 늘렸다.
# 출력은 실제로 만든 만큼만 청구되므로 평소 비용은 그대로다.
MAX_OUTPUT_TOKENS = 1500
# 요청 전체 제한(120초) 안에서 여러 번 왕복할 수 있게 한 번의 호출은 이보다 짧게 둔다.
CALL_TIMEOUT_SECONDS = 60
# 같은 입력에는 같은 도구 선택이 나오도록 무작위성을 끈다. 받지 않는 모델에는 보내지 않는다.
TEMPERATURE = 0
# 시뮬레이터와 달리 비교 조건을 고정할 필요가 없어, 한 업체가 실패하면 다른 업체로 넘긴다.
ALLOW_FALLBACKS = True

ModelCall = Callable[..., Awaitable[CallResult]]


def openrouter_transcript(
    reply: AssistantReply, results: list[tuple[ToolCall, str]]
) -> list[dict[str, Any]]:
    """Chat Completions 형식. 도구 결과는 앞선 도구 요청의 ID(tool_call_id)로 짝짓는다."""
    return [
        {
            "role": "assistant",
            "content": reply.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": json.dumps(
                            call.function.arguments, ensure_ascii=False
                        ),
                    },
                }
                for call in reply.tool_calls
            ],
        },
        *(
            {"role": "tool", "tool_call_id": call.id, "content": content}
            for call, content in results
        ),
    ]


class OpenRouterAssistantCaller:
    transcript = staticmethod(openrouter_transcript)

    def __init__(
        self,
        call_model: ModelCall,
        session: AsyncSession,
        context: AssistantCallContext,
        clock: Callable[[], datetime],
    ) -> None:
        self._call_model = call_model
        self._session = session
        self._context = context
        self._clock = clock

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AssistantReply:
        request_id = uuid.uuid4()
        routing_policy: dict[str, JsonValue] = {
            "allow_fallbacks": ALLOW_FALLBACKS,
            "data_collection": "deny",
        }
        if tools:
            routing_policy["require_parameters"] = True
        temperature = TEMPERATURE if self._context.supports_temperature else None
        execution_config: dict[str, JsonValue] = {
            "max_tokens": MAX_OUTPUT_TOKENS,
            "timeout_seconds": CALL_TIMEOUT_SECONDS,
        }
        if temperature is not None:
            execution_config["temperature"] = temperature
        await start_call(
            self._session,
            self._context,
            request_id=request_id,
            routing_policy=routing_policy,
            execution_config=execution_config,
            hashed_input=input_hash(messages, tools),
            now=self._clock(),
        )
        try:
            result = await self._call_model(
                request_id=request_id,
                model_id=self._context.openrouter_model,
                messages=messages,
                max_tokens=MAX_OUTPUT_TOKENS,
                timeout_seconds=CALL_TIMEOUT_SECONDS,
                temperature=temperature,
                allow_fallbacks=ALLOW_FALLBACKS,
                tools=tools or None,
                deny_data_collection=True,
            )
        except asyncio.CancelledError:
            # 요청 시간 초과나 연결 종료로 끊겼다. RUNNING으로 남기지 않고 닫은 뒤 취소를 이어 보낸다.
            await cancel_call(self._session, request_id, self._clock())
            raise
        await finish_call(self._session, request_id, result, self._clock())
        if result.status != CallStatus.SUCCESS:
            raise AssistantUnavailableError
        if result.truncated:
            raise AssistantReplyTruncatedError
        try:
            return AssistantReply(
                content=result.content or "",
                tool_calls=[
                    {
                        "id": call.id,
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                    for call in result.tool_calls
                ],
            )
        except ValidationError as error:
            raise AssistantUnavailableError from error

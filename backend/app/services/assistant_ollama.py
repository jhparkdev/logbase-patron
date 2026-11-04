"""로컬 Ollama의 비스트리밍 도구 호출 경계. 프롬프트와 응답은 로깅하지 않는다."""

from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.services.assistant_reply import (
    AssistantReply,
    AssistantUnavailableError,
    ToolCall,
)


class OllamaReply(BaseModel):
    message: AssistantReply
    done: bool
    done_reason: str | None = None


def ollama_transcript(
    reply: AssistantReply, results: list[tuple[ToolCall, str]]
) -> list[dict[str, Any]]:
    """Ollama 채팅 API 형식으로 모델의 도구 요청과 도구 결과를 대화에 붙인다."""
    return [
        reply.model_dump(exclude_none=True),
        *(
            {"role": "tool", "tool_name": call.function.name, "content": content}
            for call, content in results
        ),
    ]


class OllamaCaller:
    def __init__(
        self, client: httpx.AsyncClient, model: str, context_length: int
    ) -> None:
        self.client = client
        self.model = model
        self.context_length = context_length

    transcript = staticmethod(ollama_transcript)

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AssistantReply:
        try:
            response = await self.client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": self.context_length,
                        "num_predict": 768,
                        "temperature": 0,
                    },
                },
            )
            response.raise_for_status()
            if len(response.content) > 100_000:
                raise AssistantUnavailableError
            reply = OllamaReply.model_validate(response.json())
            if not reply.done or reply.done_reason == "length":
                raise AssistantUnavailableError
            if reply.message.role != "assistant":
                raise AssistantUnavailableError
            if not reply.message.content.strip() and not reply.message.tool_calls:
                raise AssistantUnavailableError
            return reply.message
        except (httpx.HTTPError, ValidationError, ValueError) as error:
            raise AssistantUnavailableError from error

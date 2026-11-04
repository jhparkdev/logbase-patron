"""로컬 Ollama의 비스트리밍 도구 호출 경계. 프롬프트와 응답은 로깅하지 않는다."""

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AssistantUnavailableError(Exception):
    pass


class ToolFunction(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any]


class ToolCall(BaseModel):
    function: ToolFunction


class OllamaMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str = "assistant"
    content: str = Field(default="", max_length=12000)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=4)


class OllamaReply(BaseModel):
    message: OllamaMessage
    done: bool
    done_reason: str | None = None


class OllamaCaller:
    def __init__(
        self, client: httpx.AsyncClient, model: str, context_length: int
    ) -> None:
        self.client = client
        self.model = model
        self.context_length = context_length

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> OllamaMessage:
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

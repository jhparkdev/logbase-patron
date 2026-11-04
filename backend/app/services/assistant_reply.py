"""도우미 대화 루프가 모델 응답을 다루는 모양. 어떤 모델 서비스를 쓰든 같은 모양으로 받는다."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_REPLY_CHARACTERS = 12000
MAX_TOOL_CALLS_PER_REPLY = 4


class AssistantUnavailableError(Exception):
    """모델 응답을 믿고 쓸 수 없어 요청을 끝내야 한다. 원인은 사용자에게 드러내지 않는다."""


class ToolFunction(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any]


class ToolCall(BaseModel):
    # OpenRouter처럼 도구 결과를 호출 ID로 짝짓는 서비스만 값을 준다.
    id: str | None = None
    function: ToolFunction


class AssistantReply(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str = "assistant"
    content: str = Field(default="", max_length=MAX_REPLY_CHARACTERS)
    tool_calls: list[ToolCall] = Field(
        default_factory=list, max_length=MAX_TOOL_CALLS_PER_REPLY
    )

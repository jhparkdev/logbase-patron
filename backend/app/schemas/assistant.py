"""보조 에이전트 계약. 대화는 요청 안에서만 사용하고 저장하지 않는다."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.models import SortOrder
from app.schemas.simulation import (
    MAX_TEXT_LENGTH,
    ExecutionConfig,
    JsonSchemaDocument,
    ModelSelectionRequest,
)
from app.schemas.usage import QueryDate, RowId
from app.services.budget_policy import BudgetStatus
from app.services.simulation_period import MAX_PERIOD_DAYS
from app.services.simulation_validation import MAX_MODEL_COUNT, MIN_MODEL_COUNT

MAX_CHAT_MESSAGES = 12
MAX_CHAT_CHARACTERS = 8000


class AssistantMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=3000)


class SimulatorState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_text: str = Field(default="", max_length=MAX_TEXT_LENGTH)
    input_text: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    json_schema: JsonSchemaDocument | None = None
    execution_config: ExecutionConfig = Field(default_factory=ExecutionConfig)
    models: list[ModelSelectionRequest] = Field(
        default_factory=list, max_length=MAX_MODEL_COUNT
    )
    scenario_id: int | None = Field(default=None, ge=1)
    has_images: bool = False


class SimulatorPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_text: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    input_text: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH)
    json_schema: JsonSchemaDocument | None = None
    execution_config: ExecutionConfig | None = None
    models: list[ModelSelectionRequest] | None = Field(
        default=None, min_length=MIN_MODEL_COUNT, max_length=MAX_MODEL_COUNT
    )

    @model_validator(mode="after")
    def has_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("변경할 설정이 필요하다")
        if "models" in self.model_fields_set and self.models is None:
            raise ValueError("모델 목록은 비울 수 없다")
        return self


class AssistantPageContext(BaseModel):
    """화면의 적용된 조회 조건만 전달한다. 자유 텍스트나 미저장 입력은 받지 않는다."""

    model_config = ConfigDict(extra="forbid")
    page: Literal[
        "customer_usage", "internal_budget", "models", "simulator", "simulation_history"
    ]
    start_date: QueryDate | None = None
    end_date: QueryDate | None = None
    customer_id: RowId | None = None
    project_id: RowId | None = None
    service_id: RowId | None = None
    model_id: RowId | None = None
    simulation_id: UUID | None = None
    section: Literal["summary", "requests", "budgets", "trend"] | None = None
    detail: bool | None = None
    budget_status: BudgetStatus | None = None

    @model_validator(mode="after")
    def valid_scope(self) -> Self:
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("시작일과 종료일을 함께 지정해야 한다")
        if (
            self.start_date
            and self.end_date
            and not 0 <= (self.end_date - self.start_date).days < MAX_PERIOD_DAYS
        ):
            raise ValueError("조회 기간이 올바르지 않다")
        scoped = {
            "customer_usage": {"customer_id", "service_id", "model_id"},
            "internal_budget": {"project_id", "model_id"},
            "models": {"model_id"},
            "simulator": {"simulation_id"},
            "simulation_history": {"model_id", "simulation_id"},
        }
        for field in {
            "customer_id",
            "project_id",
            "service_id",
            "model_id",
            "simulation_id",
        } - scoped[self.page]:
            if getattr(self, field) is not None:
                raise ValueError("현재 화면과 다른 범위의 식별자다")
        if self.budget_status is not None and self.page not in {
            "customer_usage",
            "internal_budget",
        }:
            raise ValueError("예산 상태는 사용량 화면에서만 지정한다")
        return self


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: Annotated[
        list[AssistantMessage], Field(min_length=1, max_length=MAX_CHAT_MESSAGES)
    ]
    simulator: SimulatorState | None = None
    page_context: AssistantPageContext | None = None

    @model_validator(mode="after")
    def valid_conversation(self) -> Self:
        if self.messages[-1].role != "user" or not self.messages[-1].content.strip():
            raise ValueError("마지막 메시지는 사용자 요청이어야 한다")
        if sum(len(message.content) for message in self.messages) > MAX_CHAT_CHARACTERS:
            raise ValueError("대화가 너무 길다")
        return self


class AssistantSource(BaseModel):
    title: str
    kind: Literal["models", "history", "simulation", "customer_usage", "internal_usage"]
    simulation_id: str | None = None
    requested_at: AwareDatetime | None = None
    page_context: AssistantPageContext | None = None
    page_number: int | None = Field(default=None, ge=1, le=100)
    page_size: int | None = Field(default=None, ge=1, le=100)
    sort_key: (
        Literal["requestedAt", "cost", "tokens", "confirmed", "used", "usage", "status"]
        | None
    ) = None
    sort_order: SortOrder | None = None


class AssistantChatResponse(BaseModel):
    message: str
    patch: SimulatorPatch | None = None
    sources: list[AssistantSource] = Field(default_factory=list)


class AssistantStatus(BaseModel):
    enabled: bool
    model: str


class AssistantSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulator: SimulatorState
    patch: SimulatorPatch

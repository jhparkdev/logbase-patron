"""모델 수정·상태 변경(P-03) 요청 모델."""

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import ModelStatus
from app.schemas.model_register import DisplayName, Purpose


class ModelUpdate(BaseModel):
    """PATCH /api/models/{model_id}의 본문. 보낸 항목만 바꾸고, 모델 ID와 상태 등은 받지 않는다."""

    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    # null이나 빈 글자를 보내면 용도를 비운다.
    purpose: Purpose | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_cannot_be_cleared(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("표시 이름은 비울 수 없다")
        return value

    @field_validator("purpose")
    @classmethod
    def blank_purpose_is_none(cls, value: str | None) -> str | None:
        return value or None


class ModelStatusChange(BaseModel):
    """PATCH /api/models/{model_id}/status의 본문."""

    model_config = ConfigDict(extra="forbid")

    status: ModelStatus

"""모델 등록(P-03) 요청 모델."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

MAX_OPENROUTER_MODEL_ID_LENGTH = 200
MAX_DISPLAY_NAME_LENGTH = 100
MAX_PURPOSE_LENGTH = 200

# 앞뒤 공백을 지운 뒤 검사한다. PostgreSQL은 NUL 문자가 든 문자열을 거절하므로 미리 막는다.
# 모델 ID는 '제공사/이름' 모양이다: '/' 앞뒤가 모두 비어 있지 않고 공백이 없다.
OpenRouterModelId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=MAX_OPENROUTER_MODEL_ID_LENGTH,
        pattern=r"^[^/\s\x00]+/[^\s\x00]+$",
    ),
]
DisplayName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_DISPLAY_NAME_LENGTH,
        pattern=r"^[^\x00]+$",
    ),
]
Purpose = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=MAX_PURPOSE_LENGTH,
        pattern=r"^[^\x00]*$",
    ),
]


class ModelCreate(BaseModel):
    """POST /api/models의 본문. 상태와 OpenRouter 정보는 받지 않고 서버가 정한다."""

    model_config = ConfigDict(extra="forbid")

    openrouter_model_id: OpenRouterModelId
    display_name: DisplayName
    # 비워서 보내면 없는 것(null)으로 저장한다.
    purpose: Purpose | None = None

    @field_validator("purpose")
    @classmethod
    def blank_purpose_is_none(cls, value: str | None) -> str | None:
        return value or None

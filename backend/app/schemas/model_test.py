"""모델 연결 테스트(P-03) 요청·응답 모델."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.models import ConnectionTestStatus, CostStatus, ErrorType
from app.schemas.plain_decimal import PlainDecimal

# 테스트는 실제로 비용이 드는 호출이라 문장 길이에 상한을 둔다.
MAX_TEST_PROMPT_LENGTH = 1000

# 앞뒤 공백을 지운 뒤 검사한다. PostgreSQL은 NUL 문자가 든 문자열을 거절하므로 미리 막는다.
PromptText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=MAX_TEST_PROMPT_LENGTH,
        pattern=r"^[^\x00]*$",
    ),
]


class ConnectionTestRequest(BaseModel):
    """POST /api/models/{model_id}/test의 본문. 문장을 비우면 서버의 기본 문장을 쓴다."""

    model_config = ConfigDict(extra="forbid")

    prompt: PromptText | None = None

    @field_validator("prompt")
    @classmethod
    def blank_prompt_is_none(cls, value: str | None) -> str | None:
        return value or None


class ConnectionTestResult(BaseModel):
    """테스트 결과. 실패한 테스트도 오류가 아니라 이 모양으로 돌려준다."""

    model_config = ConfigDict(from_attributes=True)

    status: ConnectionTestStatus
    tested_at: datetime
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    # 비용을 모르면 null이다(0이 아니다). 실패한 호출은 비용을 알 수 없는 것으로 기록한다.
    cost_usd: PlainDecimal | None
    cost_status: CostStatus
    actual_provider: str | None
    error_type: ErrorType | None
    # 사용자에게 그대로 보여 줄 수 있는 문구
    error_message: str | None

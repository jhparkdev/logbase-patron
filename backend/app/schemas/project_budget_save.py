"""프로젝트 월 예산 저장(P-02) 요청·응답 모델. 규칙은 고객 예산 저장(P-01)과 같다."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import AMOUNT_LIMIT, AMOUNT_MAX_DECIMAL_PLACES, Month


def _require_decimal_string(value: object) -> object:
    """금액은 문자열로만 받는다. JSON 숫자는 float을 거치며 값이 달라질 수 있다."""
    if isinstance(value, str | Decimal):
        return value
    raise ValueError("금액은 문자열이어야 한다")


class ProjectBudgetSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_amount_usd: Annotated[
        Decimal,
        BeforeValidator(_require_decimal_string),
        Field(gt=0, lt=AMOUNT_LIMIT, decimal_places=AMOUNT_MAX_DECIMAL_PLACES),
    ]
    effective_from_month: Month


class ProjectBudgetRead(BaseModel):
    budget_id: int
    project_id: int
    monthly_amount_usd: PlainDecimal
    effective_from_month: Month
    effective_to_month: Month | None

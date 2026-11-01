"""프로젝트 월 예산 저장(P-02) 요청·응답 모델. 규칙은 고객 예산 저장(P-01)과 같다."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.schemas.decimal_string import require_decimal_string
from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import AMOUNT_LIMIT, AMOUNT_MAX_DECIMAL_PLACES, Month


class ProjectBudgetSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_amount_usd: Annotated[
        Decimal,
        BeforeValidator(require_decimal_string),
        Field(gt=0, lt=AMOUNT_LIMIT, decimal_places=AMOUNT_MAX_DECIMAL_PLACES),
    ]
    effective_from_month: Month


class ProjectBudgetRead(BaseModel):
    budget_id: int
    project_id: int
    monthly_amount_usd: PlainDecimal
    effective_from_month: Month
    effective_to_month: Month | None

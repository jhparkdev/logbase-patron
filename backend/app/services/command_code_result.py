"""Command Code 조회 결과. 조회는 실패해도 예외를 던지지 않고 이 결과로 돌려준다."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.command_code import CommandCodeStatus


class UsageSnapshot(BaseModel):
    """한 구성원의 현재 결제 기간 사용량. Command Code가 일별 내역을 주지 않아 기간 합계만 있다."""

    model_config = ConfigDict(frozen=True)

    used_credits: Decimal
    request_count: int
    input_tokens: int
    output_tokens: int
    remaining_credits: Decimal
    period_start: datetime
    period_end: datetime


class FetchResult(BaseModel):
    """status가 OK일 때만 snapshot이 있다."""

    model_config = ConfigDict(frozen=True)

    status: CommandCodeStatus
    snapshot: UsageSnapshot | None = None

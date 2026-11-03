"""구성원별 Command Code 사용량(P-02) 응답 모델."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.plain_decimal import PlainDecimal


class CommandCodeStatus(StrEnum):
    """구성원 한 줄을 읽은 결과. 프론트엔드는 OK가 아니면 "불러오지 못함"으로 보여 준다."""

    OK = "OK"
    # 환경변수에 이 구성원의 Key가 없다
    KEY_MISSING = "KEY_MISSING"
    KEY_EXPIRED = "KEY_EXPIRED"
    KEY_INVALID = "KEY_INVALID"
    # 연결 실패, 서버 오류, 예상과 다른 응답. 비공식 API라 응답이 바뀌었을 수도 있다
    FETCH_FAILED = "FETCH_FAILED"


class CommandCodeMemberUsage(BaseModel):
    """구성원 한 명의 결제 기간 사용량. status가 OK가 아니면 값은 모두 null이다(0이 아니다)."""

    member_name: str
    status: CommandCodeStatus
    used_credits: PlainDecimal | None = None
    request_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    remaining_credits: PlainDecimal | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    # 우리 서버가 Command Code에 물어본 시각
    fetched_at: datetime


class CommandCodeUsageList(BaseModel):
    items: list[CommandCodeMemberUsage]

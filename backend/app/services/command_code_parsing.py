"""Command Code 응답을 읽는 순수 함수. 예상과 다른 모양은 None으로 돌려준다(비공식 API라 바뀔 수 있다)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.schemas.command_code import CommandCodeStatus
from app.services.command_code_result import UsageSnapshot

UNAUTHORIZED_STATUS = 401
# 만료된 키의 401 문구는 "Your API key has expired. Log in again ..."이다(2026-11-02 실제 조회로
# 확인, 개발자 안내와도 같다). 그때 오류 본문의 JSON 모양은 남기지 못해 error.message 위치는 틀린 키의
# 401 응답에서만 확인했다.
EXPIRED_MARKER = "expired"


def _section(body: Any, *path: str) -> Any:
    for name in path:
        if not isinstance(body, dict):
            return None
        body = body.get(name)
    return body


def _amount(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        return None
    return Decimal(value) if value >= 0 else None


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    # 시간대가 없는 시각은 기준을 알 수 없어 받지 않는다
    return parsed if parsed.tzinfo is not None else None


def parse_snapshot(
    summary: Any, credits: Any, subscription: Any
) -> UsageSnapshot | None:
    """사용량 요약·크레딧·구독 응답에서 표에 쓸 값을 뽑는다. 하나라도 읽지 못하면 None.

    남은 크레딧은 credits.monthlyCredits다. 이름만으로는 확정할 수 없어
    (사용 27.65 + 남은 62.37이 월 90에 가까워) 그렇게 추정한 것이다.
    """
    used = _amount(_section(summary, "totalCredits"))
    requests = _count(_section(summary, "totalCount"))
    tokens_in = _count(_section(summary, "totalTokensIn"))
    tokens_out = _count(_section(summary, "totalTokensOut"))
    remaining = _amount(_section(credits, "credits", "monthlyCredits"))
    start = _time(_section(subscription, "data", "currentPeriodStart"))
    end = _time(_section(subscription, "data", "currentPeriodEnd"))
    values = (used, requests, tokens_in, tokens_out, remaining, start, end)
    if any(value is None for value in values):
        return None
    return UsageSnapshot.model_validate(
        {
            "used_credits": used,
            "request_count": requests,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "remaining_credits": remaining,
            "period_start": start,
            "period_end": end,
        }
    )


def classify_error(status_code: int, body: Any) -> CommandCodeStatus:
    """오류 응답을 상태로 나눈다. 401만 키 문제로 보고, 나머지는 수집 실패다.

    403은 키가 아니라 요청 쪽 문제(User-Agent 누락 등)일 수 있어 키 오류로 보지 않는다.
    """
    if status_code != UNAUTHORIZED_STATUS:
        return CommandCodeStatus.FETCH_FAILED
    message = _section(body, "error", "message")
    if isinstance(message, str) and EXPIRED_MARKER in message.lower():
        return CommandCodeStatus.KEY_EXPIRED
    return CommandCodeStatus.KEY_INVALID

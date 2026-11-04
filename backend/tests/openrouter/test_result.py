from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.openrouter.result import (
    CallResult,
    CallStatus,
    CostSource,
    CostStatus,
    elapsed_ms,
)

STARTED_AT = datetime(2026, 10, 27, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 10, 27, 1, 0, 1, tzinfo=UTC)


def make_result(**overrides: object) -> CallResult:
    """필수 값만 채운 결과를 만든다. 필요한 값만 overrides로 바꾼다."""
    fields: dict[str, object] = {
        "status": CallStatus.FAILED,
        "requested_model": "mistralai/mistral-nemo",
        "started_at": STARTED_AT,
        "finished_at": FINISHED_AT,
        "latency_ms": 1000,
    }
    fields.update(overrides)
    return CallResult(**fields)


# ---------------------------------------------------------------
# 비용 상태와 금액은 항상 짝이 맞아야 한다 (UNKNOWN ⇔ cost_usd 없음)
# ---------------------------------------------------------------
def test_비용_상태가_UNKNOWN이면_금액은_비어_있다() -> None:
    result = make_result(cost_status=CostStatus.UNKNOWN)
    assert result.cost_usd is None


def test_비용_상태가_UNKNOWN인데_금액이_있으면_거절한다() -> None:
    with pytest.raises(ValidationError):
        make_result(cost_status=CostStatus.UNKNOWN, cost_usd=Decimal(0))


def test_비용_상태가_CONFIRMED인데_금액이_없으면_거절한다() -> None:
    with pytest.raises(ValidationError):
        make_result(cost_status=CostStatus.CONFIRMED, cost_usd=None)


def test_비용_상태가_CONFIRMED이면_금액이_0이어도_받는다() -> None:
    result = make_result(
        cost_status=CostStatus.CONFIRMED,
        cost_usd=Decimal(0),
        cost_source=CostSource.API_RESPONSE,
    )
    assert result.cost_usd == Decimal(0)


# ---------------------------------------------------------------
# 답이 잘렸는지는 finish_reason이 length인지로 알 수 있다
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("finish_reason", "expected"),
    [
        ("length", True),
        ("stop", False),
        (None, False),
    ],
)
def test_finish_reason이_length이면_답이_잘린_것이다(
    finish_reason: str | None, expected: bool
) -> None:
    result = make_result(finish_reason=finish_reason)
    assert result.truncated is expected


# ---------------------------------------------------------------
# 걸린 시간은 밀리초로 계산한다
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("seconds", "microseconds", "expected"),
    [
        (0, 0, 0),
        (1, 500000, 1500),
        (2, 0, 2000),
    ],
)
def test_걸린_시간을_밀리초로_계산한다(
    seconds: int, microseconds: int, expected: int
) -> None:
    finished_at = STARTED_AT.replace(second=seconds, microsecond=microseconds)
    assert elapsed_ms(STARTED_AT, finished_at) == expected

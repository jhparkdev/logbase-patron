from datetime import UTC, datetime

from app.openrouter.errors import USER_MESSAGES, ErrorType
from app.openrouter.failures import (
    CANCELLED_MESSAGE,
    build_cancelled_result,
    build_failure_result,
)
from app.openrouter.result import CallStatus, CostStatus

STARTED_AT = datetime(2026, 10, 27, 1, 0, 0, tzinfo=UTC)
FINISHED_AT = datetime(2026, 10, 27, 1, 0, 2, tzinfo=UTC)


def test_실패_결과는_비용_미확인이고_금액이_없다() -> None:
    result = build_failure_result(
        status=CallStatus.FAILED,
        error_type=ErrorType.PROVIDER_ERROR,
        requested_model="mistralai/mistral-nemo",
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    assert result.status == CallStatus.FAILED
    assert result.error_type == ErrorType.PROVIDER_ERROR
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.cost_source is None


def test_실패_결과의_문구는_오류_유형별_사용자용_문구다() -> None:
    result = build_failure_result(
        status=CallStatus.TIMEOUT,
        error_type=ErrorType.TIMEOUT_ERROR,
        requested_model="mistralai/mistral-nemo",
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    assert result.status == CallStatus.TIMEOUT
    assert result.error_message == USER_MESSAGES[ErrorType.TIMEOUT_ERROR]


def test_실패_결과에_걸린_시간과_상태_코드를_담는다() -> None:
    result = build_failure_result(
        status=CallStatus.FAILED,
        error_type=ErrorType.AUTH_ERROR,
        requested_model="mistralai/mistral-nemo",
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        http_status=401,
        failed_routing_step=None,
        raw_response={"error": {"code": 401}},
    )

    assert result.latency_ms == 2000
    assert result.http_status == 401
    assert result.raw_response == {"error": {"code": 401}}
    assert result.content is None
    assert result.generation_id is None


# ---------------------------------------------------------------
# 취소는 오류가 아니라 실행 상태다. 비용은 미확인으로 둔다
# ---------------------------------------------------------------
def test_취소_결과는_오류_유형이_없고_비용은_미확인이다() -> None:
    result = build_cancelled_result(
        requested_model="mistralai/mistral-nemo",
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    assert result.status == CallStatus.CANCELLED
    assert result.error_type is None
    assert result.error_message == CANCELLED_MESSAGE
    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.latency_ms == 2000
    assert result.http_status is None

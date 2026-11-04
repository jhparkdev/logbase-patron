"""schemas/usage_record.py 테스트. 고객 서비스가 보내는 호출 기록의 형식과 상태별 규칙을 본다."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import ErrorType
from app.schemas.usage_record import UsageRecordCreate

REQUESTED_AT = "2026-10-10T01:00:00Z"
COMPLETED_AT = "2026-10-10T01:00:02Z"


def record(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "request_id": str(uuid.uuid4()),
        "key_id": 1,
        "customer_code": "CUST-001",
        "task_ref": "detail-page-1001",
        "task_type": "상세페이지 생성",
        "model": "openai/gpt-4o-mini",
        "requested_at": REQUESTED_AT,
        "completed_at": COMPLETED_AT,
        "status": "SUCCESS",
    }
    body.update(overrides)
    return body


def test_a_minimal_success_record_is_accepted() -> None:
    parsed = UsageRecordCreate.model_validate(record())

    assert parsed.status == "SUCCESS"
    assert parsed.error_type is None
    assert parsed.cost_usd is None


def test_money_and_tokens_are_read_as_given() -> None:
    parsed = UsageRecordCreate.model_validate(
        record(cost_usd="0.000045", input_tokens=120, output_tokens=30)
    )

    assert parsed.cost_usd == Decimal("0.000045")
    assert (parsed.input_tokens, parsed.output_tokens) == (120, 30)


@pytest.mark.parametrize("request_id", ["not-a-uuid", "", 12345, None])
def test_the_request_id_must_be_a_uuid(request_id: Any) -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(request_id=request_id))


def test_times_must_carry_a_time_zone() -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(requested_at="2026-10-10T10:00:00"))


def test_completion_before_the_request_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(
            record(requested_at=COMPLETED_AT, completed_at=REQUESTED_AT)
        )


def test_completion_at_exactly_the_request_time_is_accepted() -> None:
    UsageRecordCreate.model_validate(record(completed_at=REQUESTED_AT))


def test_a_success_record_cannot_carry_an_error_type() -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(error_type="PROVIDER_ERROR"))


def test_a_failed_record_needs_an_error_type() -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(status="FAILED"))


def test_a_failed_record_keeps_the_error_type_it_was_given() -> None:
    parsed = UsageRecordCreate.model_validate(
        record(status="FAILED", error_type="RATE_LIMIT", http_status=429)
    )

    assert parsed.error_type == ErrorType.RATE_LIMIT
    assert parsed.http_status == 429


def test_a_timeout_record_defaults_to_the_timeout_error_type() -> None:
    parsed = UsageRecordCreate.model_validate(
        record(status="TIMEOUT", completed_at=None)
    )

    assert parsed.error_type == ErrorType.TIMEOUT_ERROR
    assert parsed.completed_at is None


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "CANCELLED", "success", ""])
def test_only_the_three_final_results_are_accepted(status: str) -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(status=status))


@pytest.mark.parametrize(
    "overrides",
    [
        {"input_tokens": -1},
        {"output_tokens": -1},
        {"cost_usd": "-0.01"},
        {"latency_ms": -1},
        {"http_status": 99},
        {"http_status": 600},
        {"key_id": 0},
    ],
)
def test_negative_or_out_of_range_numbers_are_rejected(
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(**overrides))


def test_zero_tokens_and_zero_cost_are_accepted() -> None:
    parsed = UsageRecordCreate.model_validate(
        record(input_tokens=0, output_tokens=0, cost_usd="0")
    )

    assert parsed.cost_usd == Decimal(0)


def test_cached_tokens_cannot_exceed_input_tokens() -> None:
    UsageRecordCreate.model_validate(record(input_tokens=10, cached_tokens=10))
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(input_tokens=10, cached_tokens=11))


def test_reasoning_tokens_cannot_exceed_output_tokens() -> None:
    UsageRecordCreate.model_validate(record(output_tokens=10, reasoning_tokens=10))
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(output_tokens=10, reasoning_tokens=11))


@pytest.mark.parametrize("field", ["customer_code", "task_ref", "task_type", "model"])
def test_required_text_fields_cannot_be_blank(field: str) -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(**{field: "  "}))


def test_unknown_fields_are_rejected_so_prompts_are_never_sent_by_mistake() -> None:
    with pytest.raises(ValidationError):
        UsageRecordCreate.model_validate(record(prompt="고객이 쓴 글"))

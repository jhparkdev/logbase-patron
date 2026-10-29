from decimal import Decimal

import pytest

from app.models import (
    CostSource,
    CostStatus,
    ErrorType,
    RequestStatus,
    ValidationStatus,
)
from app.openrouter import errors as openrouter_errors
from app.openrouter import result as openrouter_result
from app.services.simulation_outcome import to_slot_record
from tests.services.simulation_fakes import NOW

R = RequestStatus
V = ValidationStatus
CALL = openrouter_result.CallStatus
CALL_COST = openrouter_result.CostStatus
CALL_ERROR = openrouter_errors.ErrorType
SCHEMA = {"type": "object", "required": ["title"]}


def result(**overrides: object) -> openrouter_result.CallResult:
    """정욱님 call_model 이 돌려주는 성공 결과. 필요한 값만 덮어써서 쓴다."""
    values: dict[str, object] = {
        "status": CALL.SUCCESS,
        "content": '{"title": "a"}',
        "finish_reason": "stop",
        "requested_model": "mistralai/mistral-nemo",
        "actual_model": "mistralai/mistral-nemo",
        "provider": "DeepInfra",
        "generation_id": "gen-1",
        "prompt_tokens": 16,
        "completion_tokens": 2,
        "cached_tokens": 4,
        "cache_write_tokens": 1,
        "reasoning_tokens": 0,
        "cost_usd": Decimal("0.000000348"),
        "cost_status": CALL_COST.CONFIRMED,
        "cost_source": openrouter_result.CostSource.API_RESPONSE,
        "http_status": 200,
        "started_at": NOW,
        "finished_at": NOW,
        "latency_ms": 1830,
    }
    values.update(overrides)
    return openrouter_result.CallResult(**values)  # type: ignore[arg-type]


def failure(
    status: openrouter_result.CallStatus, **overrides: object
) -> openrouter_result.CallResult:
    """비용 미확인으로 끝난 호출. 응답 본문이 없다."""
    values: dict[str, object] = {
        "content": None,
        "finish_reason": None,
        "cost_usd": None,
        "cost_status": CALL_COST.UNKNOWN,
        "cost_source": None,
        "status": status,
    }
    values.update(overrides)
    return result(**values)


def test_successful_call_is_recorded_as_it_came() -> None:
    record = to_slot_record(result(), None)

    assert record.status == R.SUCCESS
    assert record.error_type is None
    assert (record.input_tokens, record.output_tokens) == (16, 2)
    assert record.cost_usd == Decimal("0.000000348")
    assert record.cost_status == CostStatus.CONFIRMED
    assert (record.actual_provider, record.actual_model) == (
        "DeepInfra",
        "mistralai/mistral-nemo",
    )
    assert record.latency_ms == 1830
    assert record.external_generation_id == "gen-1"
    assert record.response_text == '{"title": "a"}'
    # DB 에 칸이 있는 값은 버리지 않고 넘긴다
    assert (
        record.cached_tokens,
        record.cache_write_tokens,
        record.reasoning_tokens,
    ) == (
        4,
        1,
        0,
    )
    assert record.cost_source == CostSource.API_RESPONSE
    assert record.http_status == 200
    assert record.finish_reason == "stop"
    assert record.error_message is None


# --- 비용: 미확인은 절대 0 이 되지 않는다 ---


def test_unknown_cost_stays_null() -> None:
    record = to_slot_record(
        result(cost_status=CALL_COST.UNKNOWN, cost_usd=None, cost_source=None), None
    )

    assert (record.cost_status, record.cost_usd) == (CostStatus.UNKNOWN, None)
    assert record.cost_source is None


def test_a_real_zero_cost_is_kept_as_zero() -> None:
    # 확정된 0 USD(무료 모델)는 미확인과 다르다
    record = to_slot_record(result(cost_usd=Decimal(0)), None)

    assert (record.cost_status, record.cost_usd) == (CostStatus.CONFIRMED, Decimal(0))


# --- 실행 상태와 오류 유형 ---


@pytest.mark.parametrize("content", [None, "", "   \n"])
def test_empty_response_is_not_a_success(content: str | None) -> None:
    record = to_slot_record(result(content=content), None)

    assert record.status == R.FAILED
    assert record.error_type == ErrorType.INVALID_RESPONSE


def test_empty_response_keeps_the_cost_that_was_charged() -> None:
    # 응답이 비어 있어도 호출 비용은 나갔을 수 있다
    record = to_slot_record(result(content=""), None)

    assert record.cost_usd == Decimal("0.000000348")


def test_empty_response_says_why_it_failed() -> None:
    record = to_slot_record(result(content=""), None)

    assert (
        record.error_message
        == openrouter_errors.USER_MESSAGES[CALL_ERROR.INVALID_RESPONSE]
    )


def test_failed_call_keeps_its_error_type_and_message() -> None:
    message = openrouter_errors.USER_MESSAGES[CALL_ERROR.RATE_LIMIT]
    record = to_slot_record(
        failure(
            CALL.FAILED,
            error_type=CALL_ERROR.RATE_LIMIT,
            error_message=message,
            http_status=429,
        ),
        None,
    )

    assert (record.status, record.error_type) == (R.FAILED, ErrorType.RATE_LIMIT)
    assert (record.error_message, record.http_status) == (message, 429)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(CALL.FAILED, ErrorType.UNKNOWN_ERROR), (CALL.TIMEOUT, ErrorType.TIMEOUT_ERROR)],
)
def test_failure_without_an_error_type_gets_a_default(
    status: openrouter_result.CallStatus, expected: ErrorType
) -> None:
    # DB 는 FAILED·TIMEOUT 에 오류 유형이 반드시 있어야 한다
    record = to_slot_record(failure(status, error_type=None), None)

    assert record.error_type == expected


def test_cancelled_call_has_no_error_type() -> None:
    record = to_slot_record(
        failure(CALL.CANCELLED, error_type=CALL_ERROR.UNKNOWN_ERROR), None
    )

    assert (record.status, record.error_type) == (R.CANCELLED, None)
    assert record.cost_status == CostStatus.UNKNOWN


def test_success_never_carries_an_error_type() -> None:
    record = to_slot_record(result(error_type=CALL_ERROR.UNKNOWN_ERROR), None)

    assert (record.status, record.error_type) == (R.SUCCESS, None)


# --- JSON 검증은 응답을 받았을 때만 ---


def test_json_check_runs_on_a_successful_response() -> None:
    passed = to_slot_record(result(content='{"title": "a"}'), SCHEMA)
    failed = to_slot_record(result(content="{}"), SCHEMA)

    assert (passed.json_parse_status, passed.schema_validation_status) == (
        V.PASSED,
        V.PASSED,
    )
    assert failed.schema_validation_status == V.FAILED
    assert failed.missing_required_fields == ["title"]
    assert failed.validation_errors is not None


def test_api_success_stays_success_when_the_schema_check_fails() -> None:
    # JSON 검증 실패는 API 호출 실패와 별도다 (기준서 3.5)
    record = to_slot_record(result(content="JSON 아님"), SCHEMA)

    assert record.status == R.SUCCESS
    assert record.json_parse_status == V.FAILED


def test_json_check_is_not_applicable_without_a_schema() -> None:
    record = to_slot_record(result(content="일반 글"), None)

    assert (record.json_parse_status, record.schema_validation_status) == (
        V.NOT_APPLICABLE,
        V.NOT_APPLICABLE,
    )


@pytest.mark.parametrize("status", [CALL.FAILED, CALL.TIMEOUT, CALL.CANCELLED])
def test_json_check_is_not_executed_without_a_response(
    status: openrouter_result.CallStatus,
) -> None:
    # 응답을 받지 못한 것은 "검증 실패"가 아니라 "미실행"이다
    record = to_slot_record(
        failure(status, error_type=CALL_ERROR.PROVIDER_ERROR), SCHEMA
    )

    assert (record.json_parse_status, record.schema_validation_status) == (
        V.NOT_EXECUTED,
        V.NOT_EXECUTED,
    )
    assert record.response_text is None


def test_empty_response_means_the_json_check_was_not_executed() -> None:
    record = to_slot_record(result(content=""), SCHEMA)

    assert record.json_parse_status == V.NOT_EXECUTED

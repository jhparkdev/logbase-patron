from decimal import Decimal

import pytest

from app.models import CostStatus, ErrorType, RequestStatus, ValidationStatus
from app.services.simulation_outcome import to_slot_record
from app.services.simulation_ports import ModelCallResult

R = RequestStatus
V = ValidationStatus
SCHEMA = {"type": "object", "required": ["title"]}


def result(**overrides: object) -> ModelCallResult:
    """성공한 호출 결과. 필요한 값만 덮어써서 쓴다."""
    values: dict[str, object] = {
        "status": R.SUCCESS,
        "content": '{"title": "a"}',
        "error_type": None,
        "prompt_tokens": 16,
        "completion_tokens": 2,
        "cost_usd": Decimal("0.000000348"),
        "cost_status": CostStatus.CONFIRMED,
        "actual_model": "mistralai/mistral-nemo",
        "provider": "DeepInfra",
        "latency_ms": 1830,
        "generation_id": "gen-1",
    }
    values.update(overrides)
    return ModelCallResult(**values)  # type: ignore[arg-type]


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


# --- 비용: 미확인은 절대 0 이 되지 않는다 ---


def test_unknown_cost_stays_null() -> None:
    record = to_slot_record(result(cost_status=CostStatus.UNKNOWN, cost_usd=None), None)

    assert (record.cost_status, record.cost_usd) == (CostStatus.UNKNOWN, None)


def test_unknown_cost_with_an_amount_is_not_trusted() -> None:
    # UNKNOWN 이면 금액은 항상 null 이다 (DB 제약과 같은 규칙)
    record = to_slot_record(
        result(cost_status=CostStatus.UNKNOWN, cost_usd=Decimal(0)), None
    )

    assert record.cost_usd is None


def test_confirmed_cost_without_an_amount_becomes_unknown() -> None:
    # 금액이 없는데 확정이라고 올 수는 없다. 0 으로 채우지 않고 미확인으로 둔다
    record = to_slot_record(
        result(cost_status=CostStatus.CONFIRMED, cost_usd=None), None
    )

    assert (record.cost_status, record.cost_usd) == (CostStatus.UNKNOWN, None)


def test_estimated_cost_is_never_created_by_the_simulator() -> None:
    # 추정 비용은 정욱님 쪽에서 만든다. 시뮬레이터는 확정이 아니면 미확인으로 기록한다
    record = to_slot_record(
        result(cost_status=CostStatus.ESTIMATED, cost_usd=Decimal("0.01")), None
    )

    assert (record.cost_status, record.cost_usd) == (CostStatus.UNKNOWN, None)


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


def test_failed_call_keeps_its_error_type() -> None:
    record = to_slot_record(
        result(
            status=R.FAILED,
            content=None,
            error_type=ErrorType.RATE_LIMIT,
            cost_status=CostStatus.UNKNOWN,
            cost_usd=None,
        ),
        None,
    )

    assert (record.status, record.error_type) == (R.FAILED, ErrorType.RATE_LIMIT)


@pytest.mark.parametrize(
    ("status", "expected"),
    [(R.FAILED, ErrorType.UNKNOWN_ERROR), (R.TIMEOUT, ErrorType.TIMEOUT_ERROR)],
)
def test_failure_without_an_error_type_gets_a_default(
    status: R, expected: ErrorType
) -> None:
    # DB 는 FAILED·TIMEOUT 에 오류 유형이 반드시 있어야 한다
    record = to_slot_record(result(status=status, content=None, error_type=None), None)

    assert record.error_type == expected


def test_cancelled_call_has_no_error_type() -> None:
    record = to_slot_record(
        result(
            status=R.CANCELLED,
            content=None,
            error_type=ErrorType.UNKNOWN_ERROR,
            cost_status=CostStatus.UNKNOWN,
            cost_usd=None,
        ),
        None,
    )

    assert (record.status, record.error_type) == (R.CANCELLED, None)


def test_success_never_carries_an_error_type() -> None:
    record = to_slot_record(result(error_type=ErrorType.UNKNOWN_ERROR), None)

    assert (record.status, record.error_type) == (R.SUCCESS, None)


@pytest.mark.parametrize("status", [R.PENDING, R.RUNNING])
def test_unfinished_status_from_the_caller_is_a_failure(status: R) -> None:
    # call_model 은 끝난 상태만 돌려줘야 한다. 그렇지 않으면 RUNNING 에 남지 않게 실패로 닫는다
    record = to_slot_record(result(status=status, content=None), None)

    assert (record.status, record.error_type) == (R.FAILED, ErrorType.UNKNOWN_ERROR)


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


@pytest.mark.parametrize("status", [R.FAILED, R.TIMEOUT, R.CANCELLED])
def test_json_check_is_not_executed_without_a_response(status: R) -> None:
    # 응답을 받지 못한 것은 "검증 실패"가 아니라 "미실행"이다
    record = to_slot_record(
        result(status=status, content=None, error_type=ErrorType.PROVIDER_ERROR),
        SCHEMA,
    )

    assert (record.json_parse_status, record.schema_validation_status) == (
        V.NOT_EXECUTED,
        V.NOT_EXECUTED,
    )
    assert record.response_text is None


def test_empty_response_means_the_json_check_was_not_executed() -> None:
    record = to_slot_record(result(content=""), SCHEMA)

    assert record.json_parse_status == V.NOT_EXECUTED

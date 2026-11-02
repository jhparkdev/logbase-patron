import re

import pytest

from app.schemas.common import ErrorResponse
from app.schemas.simulation_error import (
    ERROR_SPECS,
    SimulationErrorCode,
    SimulationErrorResponse,
    error_body,
    period_error_code,
)
from app.services.simulation_period import InvalidPeriodReason

C = SimulationErrorCode

EXPECTED_STATUS = {
    C.INVALID_REQUEST: 422,
    C.INPUT_REQUIRED: 422,
    C.DUPLICATE_MODEL_SELECTION: 422,
    C.SIMULATION_NOT_FOUND: 404,
    C.SLOT_NOT_FOUND: 404,
    C.RERUN_SOURCE_NOT_FOUND: 422,
    C.SCENARIO_NOT_FOUND: 422,
    C.MODEL_NOT_FOUND: 422,
    C.MODEL_NOT_ACTIVE: 422,
    C.MODEL_IMAGE_NOT_SUPPORTED: 422,
    C.MODEL_PARAMETER_NOT_SUPPORTED: 422,
    C.IMAGE_REQUIRED: 422,
    C.IMAGE_NOT_FOUND: 422,
    C.IMAGE_EMPTY: 422,
    C.IMAGE_TOO_LARGE: 413,
    C.IMAGE_TYPE_NOT_SUPPORTED: 415,
    C.IMAGE_FILE_NOT_FOUND: 404,
    C.PROVIDER_NOT_AVAILABLE: 422,
    C.PERIOD_INCOMPLETE: 422,
    C.PERIOD_START_AFTER_END: 422,
    C.PERIOD_TOO_LONG: 422,
    C.INTERNAL_ERROR: 500,
}


@pytest.mark.parametrize(("code", "status"), EXPECTED_STATUS.items())
def test_each_code_maps_to_its_http_status(code: C, status: int) -> None:
    assert ERROR_SPECS[code].status == status


def test_every_code_has_an_expected_status() -> None:
    # 코드가 새로 생기면 이 표에도 상태를 추가하도록 강제한다
    assert set(EXPECTED_STATUS) == set(C)


def test_every_code_has_a_spec() -> None:
    assert set(ERROR_SPECS) == set(C)


@pytest.mark.parametrize("code", list(C))
def test_code_value_equals_its_name_in_upper_snake_case(code: C) -> None:
    # 프론트엔드가 문자열로 분기하므로 이름과 값이 달라지면 안 된다
    assert code.value == code.name
    assert re.fullmatch(r"[A-Z]+(_[A-Z]+)*", code.value)


def test_messages_are_not_empty_and_differ_per_code() -> None:
    messages = [spec.message for spec in ERROR_SPECS.values()]

    assert all(message.strip() for message in messages)
    assert len(set(messages)) == len(messages)


def test_server_error_message_hides_the_cause() -> None:
    # 스택 트레이스·SQL·내부 예외 메시지는 사용자에게 보이지 않는다
    message = ERROR_SPECS[C.INTERNAL_ERROR].message

    for leak in ("Traceback", "SELECT", "Exception", "sqlalchemy"):
        assert leak.lower() not in message.lower()


def test_error_body_has_only_code_and_message() -> None:
    body = error_body(C.SIMULATION_NOT_FOUND)

    assert body.model_dump(mode="json") == {
        "code": "SIMULATION_NOT_FOUND",
        "message": ERROR_SPECS[C.SIMULATION_NOT_FOUND].message,
    }


def test_error_body_is_the_common_error_shape() -> None:
    # 팀이 정한 공통 오류 형식 {code, message} 의 하위 형식이다
    assert isinstance(error_body(C.INTERNAL_ERROR), ErrorResponse)


def test_response_rejects_a_code_that_is_not_defined() -> None:
    with pytest.raises(ValueError):
        SimulationErrorResponse(code="MADE_UP", message="없는 코드")


def test_openapi_lists_every_code() -> None:
    # 프론트엔드는 코드를 따로 외우지 않고 OpenAPI 문서에서 받는다
    schema = SimulationErrorResponse.model_json_schema()

    assert schema["$defs"]["SimulationErrorCode"]["enum"] == [c.value for c in C]


def test_each_period_reason_has_its_own_code() -> None:
    codes = {period_error_code(reason) for reason in InvalidPeriodReason}

    assert len(codes) == len(InvalidPeriodReason)


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (InvalidPeriodReason.INCOMPLETE, C.PERIOD_INCOMPLETE),
        (InvalidPeriodReason.START_AFTER_END, C.PERIOD_START_AFTER_END),
        (InvalidPeriodReason.TOO_LONG, C.PERIOD_TOO_LONG),
    ],
)
def test_period_reason_maps_to_code(reason: InvalidPeriodReason, code: C) -> None:
    assert period_error_code(reason) == code
    assert ERROR_SPECS[code].status == 422

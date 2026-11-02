import json
import logging

import pytest

from app.api.simulation_errors import error_response_for
from app.schemas.simulation_error import ERROR_SPECS, SimulationErrorCode
from app.services.model_parameters import ModelParameterUnsupportedError
from app.services.simulation_cancel_service import (
    SimulationNotFoundError,
    SlotNotFoundError,
)
from app.services.simulation_create import (
    ImageNotFoundError,
    ImageRequiredError,
    ModelImageUnsupportedError,
    ModelNotActiveError,
    ModelNotFoundError,
    RerunSourceNotFoundError,
    ScenarioNotFoundError,
)
from app.services.simulation_image_check import (
    EmptyImageError,
    ImageTooLargeError,
    UnsupportedImageTypeError,
)
from app.services.simulation_image_source import StoredImageNotFoundError
from app.services.simulation_input import InputRequiredError
from app.services.simulation_lookup import SimulatorContextMissingError
from app.services.simulation_period import InvalidPeriodError, InvalidPeriodReason
from app.services.simulation_validation import (
    DuplicateModelSelectionError,
    ModelSelection,
)

C = SimulationErrorCode


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (InputRequiredError(), C.INPUT_REQUIRED),
        (
            DuplicateModelSelectionError(ModelSelection(1, "DeepInfra")),
            C.DUPLICATE_MODEL_SELECTION,
        ),
        (ScenarioNotFoundError(), C.SCENARIO_NOT_FOUND),
        (RerunSourceNotFoundError(), C.RERUN_SOURCE_NOT_FOUND),
        (ModelNotFoundError([9]), C.MODEL_NOT_FOUND),
        (ModelNotActiveError([2]), C.MODEL_NOT_ACTIVE),
        (ModelImageUnsupportedError([2]), C.MODEL_IMAGE_NOT_SUPPORTED),
        (
            ModelParameterUnsupportedError([2], ["temperature"]),
            C.MODEL_PARAMETER_NOT_SUPPORTED,
        ),
        (ImageRequiredError(), C.IMAGE_REQUIRED),
        (ImageNotFoundError([]), C.IMAGE_NOT_FOUND),
        (EmptyImageError(), C.IMAGE_EMPTY),
        (ImageTooLargeError(), C.IMAGE_TOO_LARGE),
        (UnsupportedImageTypeError(), C.IMAGE_TYPE_NOT_SUPPORTED),
        (StoredImageNotFoundError(), C.IMAGE_FILE_NOT_FOUND),
        (SimulationNotFoundError(), C.SIMULATION_NOT_FOUND),
        (SlotNotFoundError(), C.SLOT_NOT_FOUND),
        (InvalidPeriodError(InvalidPeriodReason.INCOMPLETE), C.PERIOD_INCOMPLETE),
        (InvalidPeriodError(InvalidPeriodReason.TOO_LONG), C.PERIOD_TOO_LONG),
        (
            InvalidPeriodError(InvalidPeriodReason.START_AFTER_END),
            C.PERIOD_START_AFTER_END,
        ),
    ],
)
def test_each_service_error_gets_its_code_status_and_message(
    error: Exception, code: SimulationErrorCode
) -> None:
    response = error_response_for(error)

    assert response is not None
    assert response.status_code == ERROR_SPECS[code].status
    assert json.loads(response.body) == {
        "code": code.value,
        "message": ERROR_SPECS[code].message,
    }


def test_an_error_this_module_does_not_know_is_left_to_the_common_handler() -> None:
    assert error_response_for(RuntimeError("boom")) is None
    assert error_response_for(ValueError("boom")) is None


def test_missing_simulator_setup_is_a_server_error_without_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR):
        response = error_response_for(SimulatorContextMissingError())

    assert response is not None
    assert response.status_code == ERROR_SPECS[C.INTERNAL_ERROR].status
    body = json.loads(response.body)
    assert body["code"] == C.INTERNAL_ERROR.value
    # 운영 설정 문제라 사용자에게는 일반 문구만 보이고, 원인은 서버 로그에 남긴다
    assert "PRJ-PATRON-POC" not in response.body.decode()
    assert "simulator context" in caplog.text

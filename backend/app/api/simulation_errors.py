"""시뮬레이터 서비스 예외를 {code, message} 오류 응답으로 바꾸는 곳.

서비스는 HTTP 를 모르고 도메인 예외만 던진다. 어떤 예외가 어떤 코드·상태·문구가 되는지는
이 파일 한 곳에만 둔다. 라우터마다 try/except 를 두지 않도록 라우트 클래스가 한꺼번에 잡는다.
이 파일이 모르는 예외는 그대로 올려 보내 공통 오류 처리기(api/errors.py)가 맡는다.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.schemas.simulation_error import (
    ERROR_SPECS,
    SimulationErrorCode,
    error_body,
    period_error_code,
)
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
from app.services.simulation_period import InvalidPeriodError
from app.services.simulation_validation import DuplicateModelSelectionError

logger = logging.getLogger(__name__)

C = SimulationErrorCode
# 예외 종류 하나가 코드 하나가 되는 것들. 상속 관계를 따지지 않고 정확한 종류로 찾는다
_CODE_OF_ERROR: dict[type[Exception], SimulationErrorCode] = {
    InputRequiredError: C.INPUT_REQUIRED,
    DuplicateModelSelectionError: C.DUPLICATE_MODEL_SELECTION,
    ScenarioNotFoundError: C.SCENARIO_NOT_FOUND,
    RerunSourceNotFoundError: C.RERUN_SOURCE_NOT_FOUND,
    ModelNotFoundError: C.MODEL_NOT_FOUND,
    ModelNotActiveError: C.MODEL_NOT_ACTIVE,
    ModelImageUnsupportedError: C.MODEL_IMAGE_NOT_SUPPORTED,
    ModelParameterUnsupportedError: C.MODEL_PARAMETER_NOT_SUPPORTED,
    ImageRequiredError: C.IMAGE_REQUIRED,
    ImageNotFoundError: C.IMAGE_NOT_FOUND,
    EmptyImageError: C.IMAGE_EMPTY,
    ImageTooLargeError: C.IMAGE_TOO_LARGE,
    UnsupportedImageTypeError: C.IMAGE_TYPE_NOT_SUPPORTED,
    StoredImageNotFoundError: C.IMAGE_FILE_NOT_FOUND,
    SimulationNotFoundError: C.SIMULATION_NOT_FOUND,
    SlotNotFoundError: C.SLOT_NOT_FOUND,
}


def error_response_for(error: Exception) -> JSONResponse | None:
    """시뮬레이터가 아는 예외면 오류 응답을, 모르면 None 을 돌려준다."""
    code = _code_for(error)
    if code is None:
        return None
    return JSONResponse(
        status_code=ERROR_SPECS[code].status,
        content=error_body(code).model_dump(mode="json"),
    )


def _code_for(error: Exception) -> SimulationErrorCode | None:
    if isinstance(error, InvalidPeriodError):
        return period_error_code(error.reason)
    if isinstance(error, SimulatorContextMissingError):
        # 운영 설정 문제다. 사용자에게는 일반 문구만 보이고 원인은 서버 로그에 남긴다
        logger.error("simulator context is not set up in the database")
        return C.INTERNAL_ERROR
    return _CODE_OF_ERROR.get(type(error))


class SimulationRoute(APIRoute):
    """시뮬레이터 라우터의 라우트. 서비스 예외를 오류 응답으로 바꾼다."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def translating_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except Exception as error:
                # 아는 예외만 응답으로 바꾸고 나머지는 다시 올려 공통 처리기가 맡게 한다
                response = error_response_for(error)
                if response is None:
                    raise
                return response

        return translating_handler

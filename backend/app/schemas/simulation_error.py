from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.schemas.common import ErrorCode, ErrorResponse
from app.schemas.simulation_image import MAX_IMAGE_BYTES
from app.services.simulation_period import MAX_PERIOD_DAYS, InvalidPeriodReason


class SimulationErrorCode(StrEnum):
    """시뮬레이터 API 의 오류 코드. 프론트엔드는 이 값으로 상황별로 분기한다."""

    INVALID_REQUEST = "INVALID_REQUEST"  # 형식·범위 검증 실패(모델 수 등)
    # 같은 모델·Provider 를 설정까지 같게 두 번 골랐다. 설정이 다르면 별도 비교 대상이라 허용한다
    DUPLICATE_MODEL_SELECTION = "DUPLICATE_MODEL_SELECTION"
    INPUT_REQUIRED = "INPUT_REQUIRED"  # 프롬프트 템플릿에 채울 입력 데이터가 없음
    SIMULATION_NOT_FOUND = "SIMULATION_NOT_FOUND"
    SLOT_NOT_FOUND = "SLOT_NOT_FOUND"
    RERUN_SOURCE_NOT_FOUND = "RERUN_SOURCE_NOT_FOUND"
    SCENARIO_NOT_FOUND = "SCENARIO_NOT_FOUND"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_NOT_ACTIVE = "MODEL_NOT_ACTIVE"
    # 이미지를 보냈는데 고른 모델 중에 이미지를 받지 못하는 모델이 있다
    MODEL_IMAGE_NOT_SUPPORTED = "MODEL_IMAGE_NOT_SUPPORTED"
    IMAGE_REQUIRED = "IMAGE_REQUIRED"  # 이미지가 필요한 시나리오인데 이미지가 없음
    IMAGE_NOT_FOUND = "IMAGE_NOT_FOUND"  # 올리지 않았거나 없는 asset_id
    IMAGE_EMPTY = "IMAGE_EMPTY"  # 빈 파일을 올림
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"  # 파일이 한도보다 큼
    IMAGE_TYPE_NOT_SUPPORTED = "IMAGE_TYPE_NOT_SUPPORTED"  # JPG·PNG·WebP 가 아님
    PROVIDER_NOT_AVAILABLE = "PROVIDER_NOT_AVAILABLE"
    PERIOD_INCOMPLETE = "PERIOD_INCOMPLETE"
    PERIOD_START_AFTER_END = "PERIOD_START_AFTER_END"
    PERIOD_TOO_LONG = "PERIOD_TOO_LONG"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True)
class ErrorSpec:
    """코드 하나의 HTTP 상태와 사용자에게 보여 줄 문구."""

    status: int
    message: str


# 문구에는 스택 트레이스·SQL·내부 예외 메시지·Key 를 넣지 않는다
ERROR_SPECS: dict[SimulationErrorCode, ErrorSpec] = {
    SimulationErrorCode.INVALID_REQUEST: ErrorSpec(
        422, "요청 내용이 올바르지 않습니다. 입력값을 확인해 주세요."
    ),
    SimulationErrorCode.INPUT_REQUIRED: ErrorSpec(
        422, "템플릿에 넣을 입력 데이터가 필요합니다. 입력 데이터를 입력해 주세요."
    ),
    SimulationErrorCode.DUPLICATE_MODEL_SELECTION: ErrorSpec(
        422,
        "같은 모델과 Provider 를 같은 설정으로 두 번 고를 수 없습니다. 설정을 다르게 하거나 하나를 빼 주세요.",
    ),
    SimulationErrorCode.SIMULATION_NOT_FOUND: ErrorSpec(
        404, "해당 비교 실행을 찾을 수 없습니다."
    ),
    SimulationErrorCode.SLOT_NOT_FOUND: ErrorSpec(
        404, "해당 실행에서 선택한 모델 칸을 찾을 수 없습니다."
    ),
    SimulationErrorCode.RERUN_SOURCE_NOT_FOUND: ErrorSpec(
        422, "다시 실행할 원본 비교 실행을 찾을 수 없습니다."
    ),
    SimulationErrorCode.SCENARIO_NOT_FOUND: ErrorSpec(
        422, "선택한 시나리오를 찾을 수 없습니다."
    ),
    SimulationErrorCode.MODEL_NOT_FOUND: ErrorSpec(
        422, "선택한 모델을 찾을 수 없습니다."
    ),
    SimulationErrorCode.MODEL_NOT_ACTIVE: ErrorSpec(
        422, "사용 중이 아닌 모델은 비교 실행에 쓸 수 없습니다."
    ),
    SimulationErrorCode.MODEL_IMAGE_NOT_SUPPORTED: ErrorSpec(
        422, "이미지를 지원하지 않는 모델이 있습니다. 해당 모델을 빼 주세요."
    ),
    SimulationErrorCode.IMAGE_REQUIRED: ErrorSpec(
        422, "이 시나리오는 이미지가 필요합니다. 이미지를 올려 주세요."
    ),
    SimulationErrorCode.IMAGE_NOT_FOUND: ErrorSpec(
        422, "올리지 않은 이미지가 있습니다. 이미지를 다시 올려 주세요."
    ),
    SimulationErrorCode.IMAGE_EMPTY: ErrorSpec(
        422, "빈 파일은 올릴 수 없습니다. 다른 이미지를 선택해 주세요."
    ),
    SimulationErrorCode.IMAGE_TOO_LARGE: ErrorSpec(
        413,
        f"이미지는 파일당 {MAX_IMAGE_BYTES // 1024 // 1024}MiB 이하만 올릴 수 있습니다.",
    ),
    SimulationErrorCode.IMAGE_TYPE_NOT_SUPPORTED: ErrorSpec(
        415, "JPG·PNG·WebP 이미지만 올릴 수 있습니다."
    ),
    SimulationErrorCode.PROVIDER_NOT_AVAILABLE: ErrorSpec(
        422, "선택한 모델에서 사용할 수 없는 Provider 입니다."
    ),
    SimulationErrorCode.PERIOD_INCOMPLETE: ErrorSpec(
        422, "조회 기간은 시작일과 종료일을 함께 입력해야 합니다."
    ),
    SimulationErrorCode.PERIOD_START_AFTER_END: ErrorSpec(
        422, "조회 시작일은 종료일보다 늦을 수 없습니다."
    ),
    SimulationErrorCode.PERIOD_TOO_LONG: ErrorSpec(
        422, f"조회 기간은 최대 {MAX_PERIOD_DAYS}일까지 선택할 수 있습니다."
    ),
    SimulationErrorCode.INTERNAL_ERROR: ErrorSpec(
        500, "일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    ),
}

_PERIOD_ERROR_CODES = {
    InvalidPeriodReason.INCOMPLETE: SimulationErrorCode.PERIOD_INCOMPLETE,
    InvalidPeriodReason.START_AFTER_END: SimulationErrorCode.PERIOD_START_AFTER_END,
    InvalidPeriodReason.TOO_LONG: SimulationErrorCode.PERIOD_TOO_LONG,
}


class SimulationErrorResponse(ErrorResponse):
    """공통 오류 형식 {code, message} 에서 code 를 시뮬레이터 코드로 좁힌 응답.

    라우터가 responses= 에 이 모델을 지정하면 OpenAPI 에 코드 목록(enum)이 실린다.
    """

    code: SimulationErrorCode


class SimulationRequestErrorResponse(ErrorResponse):
    """422 응답의 문서용 형식. 형식 검증 실패는 공통 코드로, 업무 규칙 위반은 시뮬레이터 코드로 나간다.

    형식 검증(모델 수, 글자 수, 정렬 키 등)은 공통 오류 처리기가 VALIDATION_ERROR 로 돌려준다.
    """

    code: Literal[ErrorCode.VALIDATION_ERROR] | SimulationErrorCode


class OriginNotAllowedResponse(ErrorResponse):
    """403 응답의 문서용 형식. 상태를 바꾸는 요청의 Origin 이 허용한 화면 주소가 아닐 때다."""

    code: Literal[ErrorCode.ORIGIN_NOT_ALLOWED]


def error_body(code: SimulationErrorCode) -> SimulationErrorResponse:
    """코드에 정해진 문구로 오류 응답 본문을 만든다."""
    return SimulationErrorResponse(code=code, message=ERROR_SPECS[code].message)


def period_error_code(reason: InvalidPeriodReason) -> SimulationErrorCode:
    return _PERIOD_ERROR_CODES[reason]

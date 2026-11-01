"""모델 관리(P-03) API의 오류 코드와 문구."""

from dataclasses import dataclass
from enum import StrEnum

from app.schemas.common import ErrorResponse


class ModelErrorCode(StrEnum):
    """프론트엔드는 이 값으로 상황별로 화면을 나눈다."""

    # OpenRouter 모델 목록을 받지 못했고 보관한 목록도 없음
    OPENROUTER_UNAVAILABLE = "OPENROUTER_UNAVAILABLE"
    # OpenRouter 모델 목록에 없는 모델 ID로 등록하려 함
    MODEL_NOT_IN_OPENROUTER = "MODEL_NOT_IN_OPENROUTER"
    # 이미 등록된 모델
    MODEL_ALREADY_REGISTERED = "MODEL_ALREADY_REGISTERED"
    # 지금 상태에서 선택한 상태로 바꿀 수 없음. 값은 StatusChangeError와 같다.
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    # 사용 중으로 바꾸려는데 24시간 안에 성공한 연결 테스트가 없음. 값은 StatusChangeError와 같다.
    TEST_NOT_PASSED = "TEST_NOT_PASSED"


@dataclass(frozen=True)
class ErrorSpec:
    """코드 하나의 HTTP 상태와 사용자에게 보여 줄 문구."""

    status: int
    message: str


# 문구에는 스택 트레이스·SQL·내부 예외 메시지·Key를 넣지 않는다
ERROR_SPECS: dict[ModelErrorCode, ErrorSpec] = {
    ModelErrorCode.OPENROUTER_UNAVAILABLE: ErrorSpec(
        502, "OpenRouter 모델 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
    ),
    ModelErrorCode.MODEL_NOT_IN_OPENROUTER: ErrorSpec(
        422, "OpenRouter에서 찾을 수 없는 모델입니다. 모델 ID를 확인해 주세요."
    ),
    ModelErrorCode.MODEL_ALREADY_REGISTERED: ErrorSpec(409, "이미 등록된 모델입니다."),
    ModelErrorCode.INVALID_STATUS_TRANSITION: ErrorSpec(
        409, "현재 상태에서는 선택한 상태로 바꿀 수 없습니다."
    ),
    ModelErrorCode.TEST_NOT_PASSED: ErrorSpec(
        409, "24시간 안에 성공한 연결 테스트가 없어 바꿀 수 없습니다."
    ),
}


class ModelErrorResponse(ErrorResponse):
    """공통 오류 형식 {code, message}에서 code를 모델 관리 코드로 좁힌 응답.

    라우터가 responses=에 이 모델을 지정하면 OpenAPI에 코드 목록(enum)이 실린다.
    """

    code: ModelErrorCode


def error_body(code: ModelErrorCode) -> ModelErrorResponse:
    """코드에 정해진 문구로 오류 응답 본문을 만든다."""
    return ModelErrorResponse(code=code, message=ERROR_SPECS[code].message)

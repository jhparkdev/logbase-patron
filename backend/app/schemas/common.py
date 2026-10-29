"""여러 도메인이 함께 쓰는 요청·응답 모델."""

from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    """오류 응답 코드. 프론트엔드는 OpenAPI enum으로 받아 코드별로 화면 처리를 나눈다."""

    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # 계정 없음·비밀번호 틀림·비활성 계정을 구분하지 않는 로그인 실패
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    # 세션 없음·만료·로그아웃됨·비활성 계정
    UNAUTHENTICATED = "UNAUTHENTICATED"
    # 허용한 화면 주소(ALLOWED_ORIGIN)가 아닌 곳에서 온 상태 변경 요청
    ORIGIN_NOT_ALLOWED = "ORIGIN_NOT_ALLOWED"


class ErrorResponse(BaseModel):
    """모든 오류 응답의 형식. message는 사용자에게 그대로 보여 줄 수 있는 문구다."""

    code: ErrorCode
    message: str

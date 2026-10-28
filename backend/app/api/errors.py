"""오류 응답을 {code, message} 한 형식으로 통일한다.

FastAPI 기본 응답은 422에 입력값을, 500에 예외 내용을 담을 수 있다. 비밀번호나 내부 정보가
응답에 나가지 않도록 모든 오류를 정해진 코드와 사용자용 문구로만 돌려준다.
"""

from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorCode, ErrorResponse

VALIDATION_MESSAGE = "입력값이 올바르지 않습니다."
INTERNAL_ERROR_MESSAGE = "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
BAD_REQUEST_MESSAGE = "요청을 처리할 수 없습니다."
# FastAPI·Starlette가 라우팅 단계에서 직접 내는 HTTP 오류
ROUTING_ERRORS: dict[int, tuple[ErrorCode, str]] = {
    status.HTTP_404_NOT_FOUND: (ErrorCode.NOT_FOUND, "요청한 경로를 찾을 수 없습니다."),
    status.HTTP_405_METHOD_NOT_ALLOWED: (
        ErrorCode.METHOD_NOT_ALLOWED,
        "허용되지 않은 요청 방식입니다.",
    ),
}


class ApiError(Exception):
    """서비스와 의존성이 정해진 오류 코드와 문구로 요청을 끝낼 때 던진다."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    status_code: int,
    code: ErrorCode,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message)
    return JSONResponse(
        body.model_dump(mode="json"), status_code=status_code, headers=headers
    )


async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.headers)


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        VALIDATION_MESSAGE,
    )


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if exc.status_code in ROUTING_ERRORS:
        code, message = ROUTING_ERRORS[exc.status_code]
    elif exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        code, message = ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE
    else:
        code, message = ErrorCode.BAD_REQUEST, BAD_REQUEST_MESSAGE
    return error_response(exc.status_code, code, message, exc.headers)


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """처리되지 않은 예외. 응답에는 내용을 넣지 않고, 서버 로그에는 Starlette가 그대로 남긴다."""
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INTERNAL_ERROR,
        INTERNAL_ERROR_MESSAGE,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)

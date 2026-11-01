"""모델 관리(P-03) 오류 코드를 {code, message} 응답으로 바꾼다."""

from fastapi.responses import JSONResponse

from app.schemas.model_error import ERROR_SPECS, ModelErrorCode, error_body


def model_error_response(code: ModelErrorCode) -> JSONResponse:
    return JSONResponse(
        status_code=ERROR_SPECS[code].status,
        content=error_body(code).model_dump(mode="json"),
    )

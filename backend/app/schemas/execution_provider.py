"""모델별 서버 업체(execution provider) 선택지(P-03) 응답 모델."""

from pydantic import BaseModel

from app.schemas.plain_decimal import PlainDecimal


class ExecutionProviderRead(BaseModel):
    """모델 하나를 처리하는 서버 업체 한 곳. 모델 제공사(예: mistralai)와는 다르다.

    execution_provider는 비교 실행 요청의 execution_provider에 그대로 쓴다.
    """

    execution_provider: str
    # OpenRouter가 주는 상태 값 그대로다. 정상일 때 0인 것은 보았지만 다른 값의 뜻은 확인하지 못했다.
    status: int | None
    # 최근 1일 가동률(%). 문자열로 내려간다.
    uptime_last_1d: PlainDecimal | None
    # 이 업체가 받는 설정 이름(예: max_tokens, temperature, response_format). 읽지 못하면 빈 목록이다
    supported_parameters: list[str]


class ExecutionProviderListResponse(BaseModel):
    items: list[ExecutionProviderRead]

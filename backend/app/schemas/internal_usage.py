"""내부 AI 예산 관리(P-02) 요청·응답 모델. 금액은 문자열, 미확인 비용은 건수로만 내려간다."""

from pydantic import BaseModel, ConfigDict

from app.schemas.plain_decimal import PlainDecimal
from app.schemas.usage import QueryDate


class InternalFilterQuery(BaseModel):
    """내부 비용 조회 조건. 기간 규칙은 오늘 날짜가 필요해 서비스가 판단한다."""

    model_config = ConfigDict(extra="forbid")

    start_date: QueryDate | None = None  # KST 달력 기준, 포함
    end_date: QueryDate | None = None  # KST 달력 기준, 포함


class InternalSummary(BaseModel):
    """비용 요약 카드. 미확인 비용은 금액에 넣지 않고 건수로만 센다."""

    api_confirmed_usd: PlainDecimal
    api_estimated_usd: PlainDecimal
    # 조회 기간이 걸치는 달의 구독료를 월 금액 그대로 더한 값이다(일별로 나누지 않는다)
    subscription_usd: PlainDecimal
    # 확정 + 추정 + 구독료
    total_managed_usd: PlainDecimal
    unknown_cost_count: int
    includes_estimate: bool
    # 비용을 모르는 호출이 있어 합계가 최종 비용이 아닐 수 있다
    has_unknown: bool

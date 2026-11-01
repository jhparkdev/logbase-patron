"""구독료(P-02) API의 오류 코드와 문구."""

from enum import StrEnum

from app.schemas.common import ErrorResponse


class SubscriptionErrorCode(StrEnum):
    """프론트엔드는 이 값으로 상황별로 화면을 나눈다."""

    # 같은 구독 식별값으로 같은 적용 월에 이미 등록됨
    SUBSCRIPTION_DUPLICATE = "SUBSCRIPTION_DUPLICATE"


DUPLICATE_MESSAGE = "이미 등록된 구독입니다. 구독 식별값과 적용 월을 확인해 주세요."


class SubscriptionErrorResponse(ErrorResponse):
    """공통 오류 형식 {code, message}에서 code를 구독료 코드로 좁힌 응답."""

    code: SubscriptionErrorCode

"""금액 입력 검증. 금액 입력 모델들이 함께 쓴다."""

from decimal import Decimal


def require_decimal_string(value: object) -> object:
    """금액은 문자열로만 받는다. JSON 숫자는 float을 거치며 값이 달라질 수 있다."""
    if isinstance(value, str | Decimal):
        return value
    raise ValueError("금액은 문자열이어야 한다")

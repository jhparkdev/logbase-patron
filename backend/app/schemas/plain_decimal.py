"""금액·단가를 JSON 문자열로 보낼 때 쓰는 Decimal 타입."""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer


def _plain_decimal(value: Decimal) -> str:
    return format(value, "f")


# 아주 작은 값이 1E-7 같은 지수 표기가 아니라 0.0000001로 나가게 한다.
# 프론트엔드는 금액을 숫자로 바꾸지 않고 문자열 그대로 다루기 때문이다.
PlainDecimal = Annotated[
    Decimal, PlainSerializer(_plain_decimal, return_type=str, when_used="json")
]

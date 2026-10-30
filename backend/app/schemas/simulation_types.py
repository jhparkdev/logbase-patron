from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

# DB 금액 칸(NUMERIC(30,18))과 같은 자릿수. 스키마는 ORM 을 가져오지 않으므로 값만 맞춘다.
MONEY_MAX_DIGITS = 30
MONEY_DECIMAL_PLACES = 18


class Page[T](BaseModel):
    """모든 목록 API 의 응답. total 은 조건에 맞는 전체 건수라 items 길이보다 클 수 있다."""

    items: list[T]
    total: int = Field(ge=0)


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        # pydantic 은 ValueError 만 검증 오류(422)로 바꾸고 TypeError 는 서버 오류로 터뜨린다
        raise ValueError("금액은 float 이 아니라 문자열로 받는다")  # noqa: TRY004
    return value


def _to_plain_string(value: Decimal) -> str:
    # str(Decimal) 은 작은 값을 "3.48E-7" 처럼 과학 표기로 내보내므로 "f" 형식으로 쓴다
    return format(value, "f")


Money = Annotated[
    Decimal,
    BeforeValidator(_reject_float),
    Field(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        allow_inf_nan=False,
    ),
    PlainSerializer(_to_plain_string, return_type=str, when_used="json"),
]
"""금액·단가. 안에서는 Decimal, API 로는 문자열이다. 비용 미확인은 `Money | None` 의 None 이다."""

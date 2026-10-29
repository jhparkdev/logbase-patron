from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.simulation_types import Money, Page


class Priced(BaseModel):
    """Money 를 필드로 쓰는 최소 모델. 비용 미확인은 None 이다."""

    cost_usd: Money | None


def test_page_has_items_and_total() -> None:
    page = Page[int](items=[1, 2], total=2)

    assert page.model_dump() == {"items": [1, 2], "total": 2}


def test_page_total_can_exceed_items_on_a_partial_page() -> None:
    # 서버가 페이지로 자르므로 전체 건수는 이번 페이지 항목 수보다 클 수 있다
    page = Page[int](items=[1, 2], total=120)

    assert len(page.items) == 2
    assert page.total == 120


def test_page_allows_empty_result() -> None:
    assert Page[int](items=[], total=0).total == 0


# 경계값: 바로 전(-1)은 거절, 정확히 그 값(0)은 허용
def test_page_total_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        Page[int](items=[], total=-1)


def test_page_validates_item_type() -> None:
    # 신뢰 경계: 타입 선언만으로 끝나지 않고 실제 값을 검증한다
    with pytest.raises(ValidationError):
        Page[int](items=["not-a-number"], total=1)


def json_cost(value: str | Decimal | None) -> str | None:
    """응답이 실제로 나가는 모양(JSON)에서 cost_usd 값만 꺼낸다."""
    return Priced(cost_usd=value).model_dump(mode="json")["cost_usd"]


def test_money_is_written_as_plain_string_not_scientific_notation() -> None:
    # OpenRouter 단가는 토큰당 소수 10자리까지 나온다. 기본 직렬화는 "3.48E-7" 이 된다
    assert json_cost(Decimal("0.000000348")) == "0.000000348"


def test_money_keeps_the_exact_digits() -> None:
    assert json_cost(Decimal("1.50")) == "1.50"
    assert json_cost(Decimal("1234567.123456")) == "1234567.123456"


def test_money_accepts_a_string_and_returns_decimal_inside() -> None:
    assert Priced(cost_usd="0.000000348").cost_usd == Decimal("0.000000348")


def test_money_unknown_cost_stays_none_never_zero() -> None:
    # cost_status=UNKNOWN <=> cost_usd IS NULL. 0 으로 바뀌면 지출이 축소되어 보고된다
    assert json_cost(None) is None


def test_money_rejects_float() -> None:
    # float 은 이미 오차가 섞인 값이라 신뢰 경계에서 거절한다
    with pytest.raises(ValidationError):
        Priced(cost_usd=0.1)


# DB 는 NUMERIC(30,18): 소수 18자리까지, 전체 30자리까지
@pytest.mark.parametrize(
    "value", ["0.000000000000000001", "999999999999.999999999999999999"]
)
def test_money_accepts_the_database_limit(value: str) -> None:
    assert json_cost(value) == value


@pytest.mark.parametrize("value", ["0.0000000000000000001", "1000000000000.0"])
def test_money_rejects_just_past_the_database_limit(value: str) -> None:
    with pytest.raises(ValidationError):
        Priced(cost_usd=value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_money_rejects_non_finite_values(value: str) -> None:
    with pytest.raises(ValidationError):
        Priced(cost_usd=value)

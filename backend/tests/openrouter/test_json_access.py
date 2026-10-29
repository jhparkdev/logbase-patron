from decimal import Decimal

import pytest

from app.openrouter.json_access import (
    get_bool,
    get_dict,
    get_int,
    get_list,
    get_number,
    get_str,
    to_number,
)


def test_dict는_없거나_모양이_다르면_빈_dict다() -> None:
    assert get_dict({"a": {"b": 1}}, "a") == {"b": 1}
    assert get_dict({"a": [1]}, "a") == {}
    assert get_dict({}, "a") == {}


def test_list는_없거나_모양이_다르면_빈_list다() -> None:
    assert get_list({"a": [1, 2]}, "a") == [1, 2]
    assert get_list({"a": {"b": 1}}, "a") == []
    assert get_list({}, "a") == []


def test_str은_문자열만_돌려준다() -> None:
    assert get_str({"a": "x"}, "a") == "x"
    assert get_str({"a": 1}, "a") is None
    assert get_str({}, "a") is None


@pytest.mark.parametrize("value", [True, False, "16", 1.5, None])
def test_int는_정수가_아니면_None이다(value: object) -> None:
    assert get_int({"a": value}, "a") is None


def test_int는_정수를_돌려준다() -> None:
    assert get_int({"a": 16}, "a") == 16
    assert get_int({"a": 0}, "a") == 0


def test_bool은_참거짓만_돌려준다() -> None:
    assert get_bool({"a": True}, "a") is True
    assert get_bool({"a": False}, "a") is False
    assert get_bool({"a": 1}, "a") is None
    assert get_bool({}, "a") is None


@pytest.mark.parametrize("value", ["0.1", "abc", True, None, [], {}])
def test_number는_숫자가_아니면_None이다(value: object) -> None:
    assert to_number(value) is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("NaN")])
def test_number는_유한하지_않은_값을_받지_않는다(value: object) -> None:
    assert to_number(value) is None


def test_number는_정수_float_Decimal을_Decimal로_돌려준다() -> None:
    assert to_number(5) == Decimal(5)
    assert to_number(3.48e-07) == Decimal("3.48e-07")
    assert to_number(Decimal("0.1")) == Decimal("0.1")


def test_get_number는_값을_꺼내_숫자로_바꾼다() -> None:
    assert get_number({"cost": 0}, "cost") == Decimal(0)
    assert get_number({}, "cost") is None

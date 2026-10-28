"""외부에서 온 JSON 값을 모양을 믿지 않고 하나씩 꺼내는 도우미.

값이 없거나 모양이 다르면 예외를 던지지 않고 None(또는 빈 값)을 돌려준다.
"""

from decimal import Decimal
from typing import Any


def get_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value
    return {}


def get_list(parent: dict[str, Any], key: str) -> list[Any]:
    value = parent.get(key)
    if isinstance(value, list):
        return value
    return []


def get_str(parent: dict[str, Any], key: str) -> str | None:
    value = parent.get(key)
    if isinstance(value, str):
        return value
    return None


def get_int(parent: dict[str, Any], key: str) -> int | None:
    value = parent.get(key)
    # True/False는 파이썬에서 int이므로 따로 걸러낸다.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def get_bool(parent: dict[str, Any], key: str) -> bool | None:
    value = parent.get(key)
    if isinstance(value, bool):
        return value
    return None


def to_number(value: Any) -> Decimal | None:
    """숫자(정수, 소수)를 Decimal로 바꾼다. 숫자가 아니거나 유한하지 않으면 None."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    # float이 와도 문자열을 거쳐 Decimal로 바꾼다. float로 계산하지는 않는다.
    number = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    if not number.is_finite():
        return None
    return number


def get_number(parent: dict[str, Any], key: str) -> Decimal | None:
    return to_number(parent.get(key))

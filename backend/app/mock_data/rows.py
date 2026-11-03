"""생성기가 만드는 행의 형태. SQL로 쓰기 전까지 테이블마다 '컬럼 이름 → 값' dict 목록으로 둔다."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import JsonValue

# 금액·단가는 Decimal만 쓴다(float 금지). JSONB 컬럼 값은 dict로 둔다.
type SqlValue = (
    None
    | bool
    | int
    | str
    | Decimal
    | datetime
    | date
    | uuid.UUID
    | list[str]
    | list[JsonValue]
    | dict[str, JsonValue]
)
type Row = dict[str, SqlValue]

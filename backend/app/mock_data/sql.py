"""생성한 행을 seed SQL로 쓴다. 컬럼 타입은 ORM 메타데이터(app.models)에서 읽는다.

트랜잭션(BEGIN/COMMIT)은 `app.cli seed`가 관리하므로 파일에 넣지 않는다.
금액은 지수 표기 없이 쓰고, 시각은 시간대가 있는 값만 받는다.
"""

import json
import uuid
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Column, Identity
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.mock_data.rows import Row, SqlValue
from app.models import Base

SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "patron_mock_data.sql"
TABLES = Base.metadata.tables
CHUNK_SIZE = 500
# 외래키가 가리키는 테이블이 먼저 오는 순서(테스트가 메타데이터로 확인한다)
TABLE_ORDER = (
    "customers",
    "projects",
    "users",
    "services",
    "api_keys",
    "command_code_keys",
    "models",
    "user_model_favorites",
    "model_prices",
    "tasks",
    "test_scenarios",
    "simulation_runs",
    "ai_requests",
    "ai_request_payloads",
    "cost_adjustments",
    "simulation_results",
    "budgets",
    "subscription_costs",
    "key_usage_snapshots",
    "usage_reconciliations",
    "change_logs",
)
HEADER = """-- =====================================================================
-- LOGBASE Patron - 시연용 Mock 데이터
-- 생성: uv --directory backend run python -m app.mock_data (직접 고치지 말고 생성기를 고친다)
-- 넣기: uv --directory backend run python -m app.cli seed
-- 모델 정보·단가는 OpenRouter 공개 모델 목록 스냅샷(backend/seed/openrouter_models_snapshot.json)이다.
-- 고객·상품·사용량은 모두 가상의 값이다. 관리자 계정은 개발 전용이다.
-- =====================================================================
"""


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _identity_column(table: str) -> str | None:
    return next(
        (c.name for c in TABLES[table].primary_key if isinstance(c.identity, Identity)),
        None,
    )


def render_value(value: SqlValue, column: Column) -> str:
    if value is None:
        return "NULL"
    if isinstance(column.type, JSONB):
        return f"{_quote(json.dumps(value, ensure_ascii=False))}::jsonb"
    if isinstance(column.type, ARRAY):
        if not isinstance(value, list):
            raise TypeError(f"{column} 배열 칸에 목록이 아닌 값이 왔다")
        if not value:
            return "'{}'::text[]"
        return "ARRAY[" + ",".join(_quote(str(item)) for item in value) + "]::text[]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError(f"{column}에 시간대 없는 시각이 왔다")
        return _quote(value.isoformat(sep=" "))
    if isinstance(value, date | uuid.UUID):
        return _quote(str(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _quote(value)
    raise TypeError(f"{column}에 쓸 수 없는 값의 형태: {type(value).__name__}")


def render_inserts(table: str, rows: list[Row], chunk_size: int = CHUNK_SIZE) -> str:
    columns = list(rows[0])
    table_columns = TABLES[table].c
    override = " OVERRIDING SYSTEM VALUE" if _identity_column(table) in columns else ""
    statements = []
    for start in range(0, len(rows), chunk_size):
        values = ",\n".join(
            "  ("
            + ", ".join(
                render_value(row[name], table_columns[name]) for name in columns
            )
            + ")"
            for row in rows[start : start + chunk_size]
        )
        statements.append(
            f"INSERT INTO {table} ({', '.join(columns)}){override} VALUES\n{values};"
        )
    return "\n\n".join(statements)


def _sequence_reset(tables: list[str]) -> str:
    lines = [
        f"  PERFORM setval(pg_get_serial_sequence('{table}', '{column}'), "
        f"(SELECT max({column}) FROM {table}));"
        for table in tables
        if (column := _identity_column(table)) is not None
    ]
    return (
        "-- 직접 ID를 넣은 테이블의 자동 번호를 이어서 쓸 수 있게 맞춤\n"
        "DO $$ BEGIN\n" + "\n".join(lines) + "\nEND $$;"
    )


def render_seed(dataset: Mapping[str, list[Row]]) -> str:
    tables = [table for table in TABLE_ORDER if dataset.get(table)]
    parts = [HEADER] + [render_inserts(table, dataset[table]) for table in tables]
    parts.append(_sequence_reset(tables))
    return "\n\n".join(parts) + "\n"

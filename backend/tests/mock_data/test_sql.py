"""app/mock_data/sql.py 테스트: 행을 seed SQL 문장으로 바꾸기."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.mock_data import sql
from app.mock_data.period import kst
from app.models import Base

TABLES = Base.metadata.tables


def _column(table: str, name: str):
    return TABLES[table].c[name]


def test_plain_values_are_quoted_safely() -> None:
    name = _column("customers", "name")

    assert sql.render_value(None, name) == "NULL"
    assert sql.render_value("it's", name) == "'it''s'"
    assert sql.render_value(True, _column("customers", "is_active")) == "true"
    assert sql.render_value(7, _column("customers", "customer_id")) == "7"


def test_money_is_written_without_exponent_or_float() -> None:
    cost = _column("ai_requests", "cost_usd")

    assert sql.render_value(Decimal("0E-12"), cost) == "0.000000000000"
    assert sql.render_value(Decimal("2.85E-8"), cost) == "0.0000000285"


def test_times_keep_their_offset_and_naive_times_are_refused() -> None:
    at = _column("ai_requests", "requested_at")

    assert sql.render_value(kst(10, 1, 12), at) == "'2026-10-01 12:00:00+09:00'"
    assert (
        sql.render_value(date(2026, 10, 1), _column("budgets", "effective_from_month"))
        == "'2026-10-01'"
    )
    with pytest.raises(ValueError):
        sql.render_value(datetime(2026, 10, 1), at)
    assert (
        sql.render_value(datetime(2026, 10, 1, tzinfo=UTC), at)
        == "'2026-10-01 00:00:00+00:00'"
    )


def test_text_arrays_and_json_get_their_postgres_types() -> None:
    params = _column("models", "supported_parameters")
    metadata = _column("models", "openrouter_metadata")
    messages = _column("ai_request_payloads", "request_messages")

    assert sql.render_value(["a", "b's"], params) == "ARRAY['a','b''s']::text[]"
    assert sql.render_value([], params) == "'{}'::text[]"
    assert (
        sql.render_value({"이름": "it's"}, metadata) == """'{"이름": "it''s"}'::jsonb"""
    )
    assert (
        sql.render_value([{"role": "user"}], messages)
        == """'[{"role": "user"}]'::jsonb"""
    )


def test_uuid_is_quoted() -> None:
    value = uuid.UUID(int=1)

    assert sql.render_value(value, _column("tasks", "task_id")) == f"'{value}'"


def test_identity_tables_override_the_generated_id() -> None:
    customers = sql.render_inserts(
        "customers", [{"customer_id": 1, "customer_code": "C", "name": "n"}]
    )
    tasks = sql.render_inserts(
        "tasks",
        [{"task_id": uuid.UUID(int=1), "usage_origin": "CUSTOMER_SERVICE", "service_id": 1,
          "task_type": "T", "data_source": "MOCK"}],
    )  # fmt: skip

    assert "OVERRIDING SYSTEM VALUE" in customers
    assert "OVERRIDING SYSTEM VALUE" not in tasks


def test_large_tables_are_split_into_several_statements() -> None:
    rows = [{"customer_id": n, "customer_code": f"C{n}", "name": "n"} for n in range(5)]

    assert sql.render_inserts("customers", rows, chunk_size=2).count("INSERT INTO") == 3


def test_table_order_inserts_referenced_tables_first() -> None:
    position = {table: index for index, table in enumerate(sql.TABLE_ORDER)}

    for table in sql.TABLE_ORDER:
        for fk in TABLES[table].foreign_keys:
            target = fk.column.table.name
            if target == table or fk.use_alter:
                continue
            assert position[target] < position[table], (table, target)


def test_seed_moves_id_counters_past_the_fixed_ids() -> None:
    text = sql.render_seed(
        {"customers": [{"customer_id": 1, "customer_code": "C", "name": "n"}]}
    )

    assert "setval(pg_get_serial_sequence('customers', 'customer_id')" in text
    assert "BEGIN;" not in text and "COMMIT" not in text

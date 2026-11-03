"""app/mock_data/dataset.py 테스트: 생성기를 모두 모은 seed 데이터의 정합성."""

import pytest
from sqlalchemy import Computed

from app.mock_data import dataset, sql
from app.models import Base

TABLES = Base.metadata.tables


@pytest.fixture(scope="module")
def data() -> dict:
    return dataset.build_dataset()


def test_every_seed_table_is_built_in_insert_order(data: dict) -> None:
    assert list(data) == [t for t in sql.TABLE_ORDER if t in data]
    assert data["ai_requests"] and data["simulation_runs"] and data["budgets"]


def test_rows_use_only_real_columns_and_skip_generated_ones(data: dict) -> None:
    for table, rows in data.items():
        columns = TABLES[table].c
        generated = {c.name for c in columns if isinstance(c.server_default, Computed)}
        for row in rows:
            assert set(row) <= set(columns.keys()), table
            assert not set(row) & generated, table


def test_required_columns_without_defaults_are_filled(data: dict) -> None:
    for table, rows in data.items():
        required = {
            c.name
            for c in TABLES[table].c
            if not c.nullable and c.server_default is None and c.default is None
        }
        for row in rows:
            missing = {name for name in required if row.get(name) is None}
            assert not missing, (table, missing)


def test_foreign_keys_point_at_rows_in_the_dataset(data: dict) -> None:
    for table, rows in data.items():
        for fk in TABLES[table].foreign_keys:
            target_table = fk.column.table.name
            # DB가 계산하는 칸(실행 설정 해시)은 seed에 없고 DB 트리거·생성 칸이 맞춘다
            if target_table not in data or isinstance(
                fk.column.server_default, Computed
            ):
                continue
            targets = {row[fk.column.name] for row in data[target_table]}
            for row in rows:
                value = row.get(fk.parent.name)
                assert value is None or value in targets, (table, fk.parent.name, value)


def test_primary_keys_are_unique(data: dict) -> None:
    for table, rows in data.items():
        keys = [tuple(row[c.name] for c in TABLES[table].primary_key) for row in rows]
        assert len(set(keys)) == len(keys), table


def test_key_last_used_time_is_its_latest_call(data: dict) -> None:
    latest: dict[int, object] = {}
    for row in data["ai_requests"]:
        latest[row["key_id"]] = max(
            latest.get(row["key_id"], row["requested_at"]), row["requested_at"]
        )

    for key in data["api_keys"]:
        assert key["last_used_at"] == latest.get(key["key_id"])


def test_total_calls_match_the_decided_scale(data: dict) -> None:
    assert 4500 <= len(data["ai_requests"]) <= 5500

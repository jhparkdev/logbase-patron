"""app/mock_data/model_catalog.py 테스트: OpenRouter 스냅샷에서 만든 모델·가격 행."""

from decimal import Decimal

import pytest

from app.mock_data import model_catalog
from app.mock_data.members import USERS
from app.mock_data.snapshot import Snapshot, load_snapshot
from app.models import ModelStatus, PriceStatus

# model_prices 단가 컬럼 NUMERIC(30,18)의 소수 자릿수
PRICE_SCALE = 18


@pytest.fixture(scope="module")
def snapshot() -> Snapshot:
    return load_snapshot()


def test_status_follows_the_lifecycle_times(snapshot: Snapshot) -> None:
    for row in model_catalog.model_rows(snapshot):
        if row["deactivated_at"] is not None:
            assert row["status"] == ModelStatus.INACTIVE
        elif row["activated_at"] is not None:
            assert row["status"] == ModelStatus.ACTIVE
        else:
            assert row["status"] == ModelStatus.TESTING


def test_model_rows_copy_the_snapshot_metadata(snapshot: Snapshot) -> None:
    by_id = {model.id: model for model in snapshot.models}

    for row in model_catalog.model_rows(snapshot):
        model = by_id[row["openrouter_model_id"]]
        assert row["provider"] == model.id.split("/")[0]
        assert row["supported_parameters"] == model.supported_parameters
        assert row["context_length"] == model.context_length
        assert row["openrouter_metadata"] == snapshot.raw_model(model.id)


def test_models_are_created_by_existing_users(snapshot: Snapshot) -> None:
    user_ids = {user.user_id for user in USERS}

    assert all(
        row["created_by"] in user_ids for row in model_catalog.model_rows(snapshot)
    )


def test_each_model_has_one_current_known_price_from_the_snapshot(
    snapshot: Snapshot,
) -> None:
    by_id = {model.id: model for model in snapshot.models}
    model_ids = {
        row["model_id"]: row["openrouter_model_id"]
        for row in model_catalog.model_rows(snapshot)
    }
    prices = model_catalog.model_price_rows(snapshot)

    assert sorted(row["model_id"] for row in prices) == sorted(model_ids)
    for row in prices:
        pricing = by_id[model_ids[row["model_id"]]].pricing
        assert row["price_status"] == PriceStatus.KNOWN
        assert row["effective_to"] is None
        assert row["execution_provider"] is None
        assert row["input_price_per_token"] == pricing.prompt
        assert row["output_price_per_token"] == pricing.completion


def test_prices_are_decimals_that_fit_the_column_scale(snapshot: Snapshot) -> None:
    columns = (
        "input_price_per_token",
        "output_price_per_token",
        "cache_read_price_per_token",
        "cache_write_price_per_token",
    )

    for row in model_catalog.model_price_rows(snapshot):
        for column in columns:
            value = row[column]
            assert value is None or isinstance(value, Decimal)
            if isinstance(value, Decimal):
                assert -value.as_tuple().exponent <= PRICE_SCALE

"""app/mock_data/snapshot.py 테스트: 커밋된 OpenRouter 스냅샷 읽기와 검증."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.mock_data.snapshot import Snapshot, load_snapshot

MODEL_WITHOUT_PRICES = (
    '{"source": "s", "fetched_at": "2026-11-03T00:00:00+09:00",'
    ' "models": [{"id": "a/b", "name": "A: B", "created": 1,'
    ' "context_length": 1, "supported_parameters": [],'
    ' "architecture": {"input_modalities": [], "output_modalities": []},'
    ' "pricing": {}}]}'
)


def test_snapshot_without_prices_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Snapshot.from_json(MODEL_WITHOUT_PRICES)


def test_committed_snapshot_records_when_it_was_fetched() -> None:
    snapshot = load_snapshot()

    assert snapshot.models
    assert snapshot.fetched_at.tzinfo is not None


def test_raw_model_keeps_the_api_notation_of_prices() -> None:
    snapshot = load_snapshot()

    for model in snapshot.models:
        raw_pricing = snapshot.raw_model(model.id)["pricing"]
        assert isinstance(raw_pricing, dict)
        assert isinstance(raw_pricing["prompt"], str)
        assert Decimal(raw_pricing["prompt"]) == model.pricing.prompt

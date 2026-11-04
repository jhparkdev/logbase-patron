"""OpenRouter 모델 목록 스냅샷(backend/seed/openrouter_models_snapshot.json)을 읽고 검증한다.

생성기와 seed는 네트워크를 쓰지 않는다. 스냅샷은 사람이 공개 API(/api/v1/models)에서 받아 커밋한다.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Self

from pydantic import BaseModel, JsonValue, PrivateAttr

SNAPSHOT_FILE = (
    Path(__file__).resolve().parents[2] / "seed" / "openrouter_models_snapshot.json"
)


class SnapshotPricing(BaseModel):
    """토큰당 단가(USD). API가 문자열로 주므로 Decimal로 받아 float을 거치지 않는다."""

    prompt: Decimal
    completion: Decimal
    input_cache_read: Decimal | None = None
    input_cache_write: Decimal | None = None


class SnapshotArchitecture(BaseModel):
    input_modalities: list[str]
    output_modalities: list[str]


class SnapshotModel(BaseModel):
    id: str
    name: str
    created: int  # 출시 시각(Unix 초)
    context_length: int
    architecture: SnapshotArchitecture
    pricing: SnapshotPricing
    supported_parameters: list[str]


class _RawSnapshot(BaseModel):
    models: list[dict[str, JsonValue]]


class Snapshot(BaseModel):
    source: str
    fetched_at: datetime
    models: list[SnapshotModel]
    _raw: dict[str, dict[str, JsonValue]] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_json(cls, text: str) -> Self:
        snapshot = cls.model_validate_json(text)
        raw = _RawSnapshot.model_validate_json(text)
        snapshot._raw = {
            model.id: entry
            for model, entry in zip(snapshot.models, raw.models, strict=True)
        }
        return snapshot

    def raw_model(self, model_id: str) -> dict[str, JsonValue]:
        """API 응답 원문. 단가 문자열 같은 값의 표기를 바꾸지 않고 DB JSONB에 넣는다."""
        return self._raw[model_id]


def load_snapshot(path: Path = SNAPSHOT_FILE) -> Snapshot:
    return Snapshot.from_json(path.read_text(encoding="utf-8"))

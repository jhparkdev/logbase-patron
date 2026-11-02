from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.openrouter.image_result import GeneratedImage, ImageCallResult
from app.openrouter.result import CallStatus, CostStatus

STARTED_AT = datetime(2026, 11, 2, 1, 0, 0, tzinfo=UTC)
IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000


def make(**overrides: object) -> ImageCallResult:
    fields: dict[str, object] = {
        "status": CallStatus.SUCCESS,
        "requested_model": "bytedance-seed/seedream-4.5",
        "started_at": STARTED_AT,
        "finished_at": STARTED_AT,
        "latency_ms": 0,
    }
    fields.update(overrides)
    return ImageCallResult.model_validate(fields)


def test_비용_미확인이면_금액이_없어야_한다() -> None:
    with pytest.raises(ValidationError):
        make(cost_status=CostStatus.UNKNOWN, cost_usd=Decimal(0))


def test_비용_확정이면_금액이_있어야_한다() -> None:
    with pytest.raises(ValidationError):
        make(cost_status=CostStatus.CONFIRMED, cost_usd=None)


def test_기본값은_비용_미확인이고_이미지가_없다() -> None:
    result = make()

    assert result.cost_status == CostStatus.UNKNOWN
    assert result.cost_usd is None
    assert result.images == ()


def test_결과를_문자열로_바꿔도_이미지_내용은_나오지_않는다() -> None:
    result = make(images=(GeneratedImage(data=IMAGE_BYTES, media_type="image/png"),))

    assert "PNG" not in repr(result)
    assert "\\x00" not in repr(result)

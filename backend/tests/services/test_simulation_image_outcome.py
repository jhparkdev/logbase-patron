from decimal import Decimal

import pytest

from app.models import (
    CostSource,
    CostStatus,
    ErrorType,
    RequestStatus,
    ValidationStatus,
)
from app.openrouter import errors as openrouter_errors
from app.openrouter import result as openrouter_result
from app.openrouter.image_result import GeneratedImage, ImageCallResult
from app.services.simulation_image_outcome import to_image_slot_record
from tests.services.simulation_fakes import NOW

R = RequestStatus
V = ValidationStatus
CALL = openrouter_result.CallStatus
CALL_COST = openrouter_result.CostStatus
CALL_ERROR = openrouter_errors.ErrorType
PNG = GeneratedImage(data=b"\x89PNG\r\n\x1a\n", media_type="image/png")


def result(**overrides: object) -> ImageCallResult:
    """generate_image 가 돌려주는 성공 결과. 필요한 값만 덮어써서 쓴다."""
    values: dict[str, object] = {
        "status": CALL.SUCCESS,
        "images": (PNG,),
        "requested_model": "bytedance-seed/seedream-4.5",
        "generation_id": "gen-img1",
        "prompt_tokens": 12,
        "completion_tokens": 4096,
        "total_tokens": 4108,
        "image_tokens": 4096,
        "cost_usd": Decimal("0.04"),
        "cost_status": CALL_COST.CONFIRMED,
        "cost_source": openrouter_result.CostSource.API_RESPONSE,
        "http_status": 200,
        "started_at": NOW,
        "finished_at": NOW,
        "latency_ms": 8000,
    }
    values.update(overrides)
    return ImageCallResult(**values)  # type: ignore[arg-type]


def failure(
    status: openrouter_result.CallStatus, **overrides: object
) -> ImageCallResult:
    """비용 미확인으로 끝난 호출. 이미지가 없다."""
    values: dict[str, object] = {
        "images": (),
        "cost_usd": None,
        "cost_status": CALL_COST.UNKNOWN,
        "cost_source": None,
        "generation_id": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "image_tokens": None,
        "status": status,
    }
    values.update(overrides)
    return result(**values)


def test_성공은_확정_비용과_토큰을_그대로_옮긴다() -> None:
    record = to_image_slot_record(result())

    assert record.status == R.SUCCESS
    assert record.error_type is None
    assert record.error_message is None
    assert record.http_status == 200
    assert record.cost_status == CostStatus.CONFIRMED
    assert record.cost_usd == Decimal("0.04")
    assert record.cost_source == CostSource.API_RESPONSE
    assert record.input_tokens == 12
    assert record.output_tokens == 4096
    assert record.latency_ms == 8000
    assert record.external_generation_id == "gen-img1"


def test_응답에_없는_값은_채우지_않는다() -> None:
    record = to_image_slot_record(result())

    # 이미지 응답에는 실제 모델·업체가 없다. 요청한 값으로 지어내지 않는다
    assert record.actual_model is None
    assert record.actual_provider is None
    assert record.finish_reason is None
    assert record.cached_tokens is None
    assert record.cache_write_tokens is None
    assert record.reasoning_tokens is None


def test_응답_글은_없고_JSON_검증은_미적용이다() -> None:
    record = to_image_slot_record(result())

    assert record.response_text is None
    assert record.json_parse_status == V.NOT_APPLICABLE
    assert record.schema_validation_status == V.NOT_APPLICABLE
    assert record.missing_required_fields is None
    assert record.validation_errors is None


def test_비용이_없으면_0이_아니라_미확인이다() -> None:
    record = to_image_slot_record(
        result(cost_usd=None, cost_status=CALL_COST.UNKNOWN, cost_source=None)
    )

    assert record.status == R.SUCCESS
    assert record.cost_status == CostStatus.UNKNOWN
    assert record.cost_usd is None
    assert record.cost_source is None


def test_이미지가_없는_성공은_성공으로_보지_않는다() -> None:
    record = to_image_slot_record(result(images=()))

    invalid = CALL_ERROR.INVALID_RESPONSE
    assert record.status == R.FAILED
    assert record.error_type == ErrorType.INVALID_RESPONSE
    assert record.error_message == openrouter_errors.USER_MESSAGES[invalid]


def test_응답이_깨진_실패도_받은_비용은_남긴다() -> None:
    invalid = CALL_ERROR.INVALID_RESPONSE
    record = to_image_slot_record(
        result(
            status=CALL.FAILED,
            images=(),
            error_type=invalid,
            error_message=openrouter_errors.USER_MESSAGES[invalid],
        )
    )

    assert record.status == R.FAILED
    assert record.error_type == ErrorType.INVALID_RESPONSE
    assert record.cost_status == CostStatus.CONFIRMED
    assert record.cost_usd == Decimal("0.04")


@pytest.mark.parametrize(
    ("status", "error", "expected_status", "expected_error"),
    [
        (CALL.FAILED, CALL_ERROR.PROVIDER_ERROR, R.FAILED, ErrorType.PROVIDER_ERROR),
        (CALL.TIMEOUT, CALL_ERROR.TIMEOUT_ERROR, R.TIMEOUT, ErrorType.TIMEOUT_ERROR),
        (CALL.FAILED, None, R.FAILED, ErrorType.UNKNOWN_ERROR),
        (CALL.TIMEOUT, None, R.TIMEOUT, ErrorType.TIMEOUT_ERROR),
    ],
)
def test_실패는_오류_유형을_반드시_담는다(
    status: openrouter_result.CallStatus,
    error: openrouter_errors.ErrorType | None,
    expected_status: RequestStatus,
    expected_error: ErrorType,
) -> None:
    record = to_image_slot_record(
        failure(status, error_type=error, error_message="문구")
    )

    assert record.status == expected_status
    assert record.error_type == expected_error
    assert record.error_message == "문구"
    assert record.cost_status == CostStatus.UNKNOWN
    assert record.cost_usd is None


def test_취소는_오류_유형_없이_문구만_남긴다() -> None:
    record = to_image_slot_record(
        failure(CALL.CANCELLED, error_message="호출이 취소되었습니다.")
    )

    assert record.status == R.CANCELLED
    assert record.error_type is None
    assert record.error_message == "호출이 취소되었습니다."
    assert record.cost_status == CostStatus.UNKNOWN
    assert record.cost_usd is None

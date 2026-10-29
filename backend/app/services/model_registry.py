"""등록 모델(P-03)의 규칙. DB 없이 판단하는 순수 함수만 둔다."""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.models import ConnectionTestStatus, ModelStatus

# OpenRouter 가격 항목 이름 -> 우리 가격 칸
PROMPT_KEY = "prompt"
COMPLETION_KEY = "completion"
CACHE_READ_KEY = "input_cache_read"
CACHE_WRITE_KEY = "input_cache_write"

RESPONSE_FORMAT_PARAMETER = "response_format"

# 관리자가 바꿀 수 있는 전이. 같은 상태로의 변경과 TESTING으로 돌아가는 전이는 없다.
ALLOWED_TRANSITIONS = {
    (ModelStatus.TESTING, ModelStatus.ACTIVE),
    (ModelStatus.TESTING, ModelStatus.INACTIVE),
    (ModelStatus.ACTIVE, ModelStatus.INACTIVE),
    (ModelStatus.INACTIVE, ModelStatus.ACTIVE),
}


class StatusChangeError(StrEnum):
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    TEST_NOT_PASSED = "TEST_NOT_PASSED"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    SUSPECTED_DISCONTINUED = "SUSPECTED_DISCONTINUED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PriceSnapshot:
    """토큰 1개당 단가. 같은 값인지 비교해 가격이 바뀌었는지 판단한다."""

    input_price_per_token: Decimal
    output_price_per_token: Decimal
    cache_read_price_per_token: Decimal | None
    cache_write_price_per_token: Decimal | None


def check_status_change(
    current: str, target: str, last_test_status: str | None
) -> StatusChangeError | None:
    """상태를 바꿀 수 있으면 None, 아니면 거절 사유를 돌려준다.

    ACTIVE로 바꾸려면 마지막 연결 테스트가 성공이어야 한다 (U-29: 마지막 테스트 기준).
    """
    if (current, target) not in ALLOWED_TRANSITIONS:
        return StatusChangeError.INVALID_STATUS_TRANSITION
    if (
        target == ModelStatus.ACTIVE
        and last_test_status != ConnectionTestStatus.SUCCESS
    ):
        return StatusChangeError.TEST_NOT_PASSED
    return None


def judge_availability(
    openrouter_model_id: str, listed_model_ids: Collection[str] | None
) -> AvailabilityStatus:
    """OpenRouter 모델 목록과 비교해 제공 중단이 의심되는지 판단한다.

    목록을 받지 못했거나 비어 있으면 조회가 잘못된 것으로 보고 판단하지 않는다.
    """
    if not listed_model_ids:
        return AvailabilityStatus.UNKNOWN
    if openrouter_model_id in listed_model_ids:
        return AvailabilityStatus.AVAILABLE
    return AvailabilityStatus.SUSPECTED_DISCONTINUED


def supports_json_schema(supported_parameters: Collection[str]) -> bool:
    return RESPONSE_FORMAT_PARAMETER in supported_parameters


def provider_from_model_id(openrouter_model_id: str) -> str | None:
    """모델 ID의 '/' 앞부분을 모델 제공사로 쓴다 (안). '/'가 없으면 None."""
    provider, separator, _ = openrouter_model_id.partition("/")
    if not separator or not provider:
        return None
    return provider


def snapshot_from_pricing(pricing: Mapping[str, Decimal]) -> PriceSnapshot | None:
    """OpenRouter 가격 항목에서 우리가 저장하는 단가를 꺼낸다.

    입력 또는 출력 단가가 없으면 가격 미확인이라 None이다.
    """
    prompt = pricing.get(PROMPT_KEY)
    completion = pricing.get(COMPLETION_KEY)
    if prompt is None or completion is None:
        return None
    return PriceSnapshot(
        input_price_per_token=prompt,
        output_price_per_token=completion,
        cache_read_price_per_token=pricing.get(CACHE_READ_KEY),
        cache_write_price_per_token=pricing.get(CACHE_WRITE_KEY),
    )


def price_changed(current: PriceSnapshot | None, new: PriceSnapshot) -> bool:
    """새 단가가 현재 단가와 다르면 True. 처음 받은 가격(current가 None)도 True."""
    return current != new

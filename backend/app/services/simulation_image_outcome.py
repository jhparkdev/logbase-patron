from decimal import Decimal

from app.models import CostSource, CostStatus, ErrorType, RequestStatus
from app.openrouter import errors as openrouter_errors
from app.openrouter.image_result import ImageCallResult
from app.openrouter.result import CostStatus as CallCostStatus
from app.services.simulation_json_check import check_json_output
from app.services.simulation_ports import SlotRecord

_DEFAULT_ERROR_TYPE = {
    RequestStatus.FAILED: ErrorType.UNKNOWN_ERROR,
    RequestStatus.TIMEOUT: ErrorType.TIMEOUT_ERROR,
}


def to_image_slot_record(result: ImageCallResult) -> SlotRecord:
    """generate_image 결과를 저장할 값으로 바꾼다. DB 제약을 어기는 조합이 나가지 않게 정리한다.

    이미지 응답에 없는 값(실제 모델·업체, 캐시·추론 토큰)은 요청한 값으로 채우지 않고 비워 둔다.
    이미지 내용은 여기서 다루지 않는다. 저장소에 따로 저장한다.
    """
    status, error_type, error_message = _status_and_error(result)
    cost_status, cost_usd, cost_source = _cost(result)
    # 이미지에는 JSON Schema 가 없으므로 검증은 "미적용"이다
    check = check_json_output(None, None)
    return SlotRecord(
        status=status,
        error_type=error_type,
        error_message=error_message,
        http_status=result.http_status,
        finish_reason=None,
        response_text=None,
        # 이미지 토큰은 출력 토큰에 포함되어 온다
        input_tokens=result.prompt_tokens,
        output_tokens=result.completion_tokens,
        cached_tokens=None,
        cache_write_tokens=None,
        reasoning_tokens=None,
        cost_usd=cost_usd,
        cost_status=cost_status,
        cost_source=cost_source,
        actual_provider=None,
        actual_model=None,
        latency_ms=result.latency_ms,
        external_generation_id=result.generation_id,
        json_parse_status=check.json_parse_status,
        schema_validation_status=check.schema_validation_status,
        missing_required_fields=check.missing_required_fields,
        validation_errors=check.validation_errors,
    )


def _status_and_error(
    result: ImageCallResult,
) -> tuple[RequestStatus, ErrorType | None, str | None]:
    status = RequestStatus(result.status.value)
    if status == RequestStatus.SUCCESS:
        if not result.images:
            # 이미지가 없는 응답을 성공으로 보지 않는다
            invalid = openrouter_errors.ErrorType.INVALID_RESPONSE
            return (
                RequestStatus.FAILED,
                ErrorType(invalid.value),
                openrouter_errors.USER_MESSAGES[invalid],
            )
        return RequestStatus.SUCCESS, None, None
    if status == RequestStatus.CANCELLED:
        return RequestStatus.CANCELLED, None, result.error_message
    error_type = (
        ErrorType(result.error_type.value)
        if result.error_type is not None
        else _DEFAULT_ERROR_TYPE[status]
    )
    return status, error_type, result.error_message


def _cost(
    result: ImageCallResult,
) -> tuple[CostStatus, Decimal | None, CostSource | None]:
    """확정 비용만 기록한다. 미확인은 금액도 근거도 없다(null). 0 으로 채우지 않는다.

    실패한 호출이어도 받은 비용은 남긴다. 이미지 응답에는 호출 ID가 없어 나중에 대조하기 어렵다.
    """
    if result.cost_status != CallCostStatus.CONFIRMED:
        return CostStatus.UNKNOWN, None, None
    source = CostSource(result.cost_source.value) if result.cost_source else None
    return CostStatus.CONFIRMED, result.cost_usd, source

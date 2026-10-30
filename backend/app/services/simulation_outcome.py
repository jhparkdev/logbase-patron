from decimal import Decimal
from typing import Any

from app.models import CostSource, CostStatus, ErrorType, RequestStatus
from app.openrouter import errors as openrouter_errors
from app.openrouter.result import CallResult
from app.openrouter.result import CostStatus as CallCostStatus
from app.services.simulation_json_check import check_json_output
from app.services.simulation_ports import SlotRecord

_DEFAULT_ERROR_TYPE = {
    RequestStatus.FAILED: ErrorType.UNKNOWN_ERROR,
    RequestStatus.TIMEOUT: ErrorType.TIMEOUT_ERROR,
}


def to_slot_record(
    result: CallResult, json_schema: dict[str, Any] | None
) -> SlotRecord:
    """call_model 결과를 저장할 값으로 바꾼다. DB 제약을 어기는 조합이 나가지 않게 정리한다.

    call_model 의 상태·오류·비용 값은 DB 값과 이름이 같아 그대로 옮긴다.
    """
    status, error_type, error_message = _status_and_error(result)
    cost_status, cost_usd, cost_source = _cost(result)
    # 응답을 받은 성공 호출만 JSON 을 검증한다. 그 밖에는 "미실행"(Schema 가 없으면 "미적용")이다
    check = check_json_output(
        result.content if status == RequestStatus.SUCCESS else None, json_schema
    )
    return SlotRecord(
        status=status,
        error_type=error_type,
        error_message=error_message,
        http_status=result.http_status,
        finish_reason=result.finish_reason,
        response_text=result.content,
        input_tokens=result.prompt_tokens,
        output_tokens=result.completion_tokens,
        cached_tokens=result.cached_tokens,
        cache_write_tokens=result.cache_write_tokens,
        reasoning_tokens=result.reasoning_tokens,
        cost_usd=cost_usd,
        cost_status=cost_status,
        cost_source=cost_source,
        actual_provider=result.provider,
        actual_model=result.actual_model,
        latency_ms=result.latency_ms,
        external_generation_id=result.generation_id,
        json_parse_status=check.json_parse_status,
        schema_validation_status=check.schema_validation_status,
        missing_required_fields=check.missing_required_fields,
        validation_errors=check.validation_errors,
    )


def _status_and_error(
    result: CallResult,
) -> tuple[RequestStatus, ErrorType | None, str | None]:
    status = RequestStatus(result.status.value)
    if status == RequestStatus.SUCCESS:
        if not (result.content and result.content.strip()):
            # 빈 응답을 성공으로 보지 않는다
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


def _cost(result: CallResult) -> tuple[CostStatus, Decimal | None, CostSource | None]:
    """확정 비용만 기록한다. 미확인은 금액도 근거도 없다(null). 0 으로 채우지 않는다."""
    if result.cost_status != CallCostStatus.CONFIRMED:
        return CostStatus.UNKNOWN, None, None
    source = CostSource(result.cost_source.value) if result.cost_source else None
    return CostStatus.CONFIRMED, result.cost_usd, source

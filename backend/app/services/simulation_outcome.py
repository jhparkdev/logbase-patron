from typing import Any

from app.models import CostStatus, ErrorType, RequestStatus
from app.services.simulation_json_check import check_json_output
from app.services.simulation_ports import ModelCallResult, SlotRecord

_DEFAULT_ERROR_TYPE = {
    RequestStatus.FAILED: ErrorType.UNKNOWN_ERROR,
    RequestStatus.TIMEOUT: ErrorType.TIMEOUT_ERROR,
}
_UNFINISHED = {RequestStatus.PENDING, RequestStatus.RUNNING}


def to_slot_record(
    result: ModelCallResult, json_schema: dict[str, Any] | None
) -> SlotRecord:
    """call_model 결과를 저장할 값으로 바꾼다. DB 제약을 어기는 조합이 나가지 않게 정리한다."""
    status, error_type = _status_and_error(result)
    cost_status, cost_usd = _cost(result)
    # 응답을 받은 성공 호출만 JSON 을 검증한다. 그 밖에는 "미실행"(Schema 가 없으면 "미적용")이다
    check = check_json_output(
        result.content if status == RequestStatus.SUCCESS else None, json_schema
    )
    return SlotRecord(
        status=status,
        error_type=error_type,
        response_text=result.content,
        input_tokens=result.prompt_tokens,
        output_tokens=result.completion_tokens,
        cost_usd=cost_usd,
        cost_status=cost_status,
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
    result: ModelCallResult,
) -> tuple[RequestStatus, ErrorType | None]:
    status = result.status
    if status in _UNFINISHED:
        # call_model 은 끝난 상태만 돌려줘야 한다. RUNNING 에 남지 않게 실패로 닫는다
        return RequestStatus.FAILED, ErrorType.UNKNOWN_ERROR
    if status == RequestStatus.SUCCESS:
        if not (result.content and result.content.strip()):
            # 빈 응답을 성공으로 보지 않는다
            return RequestStatus.FAILED, ErrorType.INVALID_RESPONSE
        return RequestStatus.SUCCESS, None
    if status == RequestStatus.CANCELLED:
        return RequestStatus.CANCELLED, None
    return status, result.error_type or _DEFAULT_ERROR_TYPE[status]


def _cost(result: ModelCallResult) -> tuple[CostStatus, Any]:
    """확정 비용만 기록한다. 금액이 없거나 확정이 아니면 미확인(null)이고 0 으로 채우지 않는다."""
    if result.cost_status == CostStatus.CONFIRMED and result.cost_usd is not None:
        return CostStatus.CONFIRMED, result.cost_usd
    return CostStatus.UNKNOWN, None

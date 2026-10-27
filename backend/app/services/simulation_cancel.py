from enum import StrEnum

from app.services.simulation_status import RequestStatus


class CancelDecision(StrEnum):
    CANCEL = "CANCEL"
    ALREADY_CANCELLED = "ALREADY_CANCELLED"
    ALREADY_TERMINAL = "ALREADY_TERMINAL"


_CANCELLABLE = {RequestStatus.PENDING, RequestStatus.RUNNING}


def decide_request_cancel(status: RequestStatus) -> CancelDecision:
    """모델별 취소 요청을 현재 상태 기준으로 어떻게 처리할지 판정한다."""
    if status in _CANCELLABLE:
        return CancelDecision.CANCEL
    if status == RequestStatus.CANCELLED:
        return CancelDecision.ALREADY_CANCELLED
    return CancelDecision.ALREADY_TERMINAL

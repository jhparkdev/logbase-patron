from collections.abc import Sequence

from app.models import RequestStatus, SimulationStatus

_NOT_FINISHED = {RequestStatus.PENDING, RequestStatus.RUNNING}


def compute_overall_status(statuses: Sequence[RequestStatus]) -> SimulationStatus:
    """모델별 실행 상태 목록에서 Simulation 전체 상태를 계산한다."""
    if not statuses:
        raise ValueError("모델별 상태가 비어 있어 전체 상태를 계산할 수 없다")

    if all(s == RequestStatus.PENDING for s in statuses):
        return SimulationStatus.PENDING
    if any(s in _NOT_FINISHED for s in statuses):
        return SimulationStatus.RUNNING
    if all(s == RequestStatus.SUCCESS for s in statuses):
        return SimulationStatus.SUCCESS
    if any(s == RequestStatus.SUCCESS for s in statuses):
        return SimulationStatus.PARTIAL_SUCCESS
    if all(s == RequestStatus.CANCELLED for s in statuses):
        return SimulationStatus.CANCELLED
    return SimulationStatus.FAILED

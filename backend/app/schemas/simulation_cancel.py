from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models import RequestStatus, SimulationStatus
from app.services.simulation_cancel import CancelDecision
from app.services.simulation_validation import MAX_MODEL_COUNT

_FINISHED = {RequestStatus.SUCCESS, RequestStatus.FAILED, RequestStatus.TIMEOUT}


class RequestCancelOutcome(BaseModel):
    """모델 한 칸의 취소 처리 결과. decision 은 decide_request_cancel 이 내린 판정이다.

    비용은 싣지 않는다. 취소된 호출의 비용은 대조(reconcile) 전까지 미확인이라 여기서 0 으로 보일 수 있다.
    """

    request_id: UUID
    slot_no: Annotated[int, Field(ge=1, le=MAX_MODEL_COUNT)]
    decision: CancelDecision
    status: RequestStatus  # 처리 뒤 이 칸의 상태

    @model_validator(mode="after")
    def _status_matches_decision(self) -> Self:
        # CANCEL 직후 상태는 취소 방식(즉시 전이 여부)이 정해진 뒤에 제약한다
        if (
            self.decision == CancelDecision.ALREADY_CANCELLED
            and self.status != RequestStatus.CANCELLED
        ):
            raise ValueError("ALREADY_CANCELLED 는 상태가 CANCELLED 여야 한다")
        if (
            self.decision == CancelDecision.ALREADY_TERMINAL
            and self.status not in _FINISHED
        ):
            raise ValueError("ALREADY_TERMINAL 은 SUCCESS·FAILED·TIMEOUT 상태여야 한다")
        return self


class SimulationCancelResponse(BaseModel):
    """취소 요청 응답. 실행 전체 취소는 칸 전부를, 모델 하나 취소는 그 칸 하나를 담는다."""

    simulation_id: UUID
    status: SimulationStatus  # 처리 뒤 실행 전체 상태
    results: Annotated[
        list[RequestCancelOutcome], Field(min_length=1, max_length=MAX_MODEL_COUNT)
    ]

    @model_validator(mode="after")
    def _one_outcome_per_slot(self) -> Self:
        slots = [outcome.slot_no for outcome in self.results]
        if len(slots) != len(set(slots)):
            raise ValueError("slot_no 가 중복되었다. 칸마다 처리 결과는 하나여야 한다")
        return self

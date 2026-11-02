from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    JsonValue,
    computed_field,
    model_validator,
)

from app.models import (
    CostStatus,
    ErrorType,
    ModelStatus,
    RequestStatus,
    SimulationStatus,
    TestType,
    ValidationStatus,
)
from app.schemas.simulation_output import OutputImageRead, OutputType
from app.schemas.simulation_types import Money
from app.services.simulation_validation import MAX_MODEL_COUNT, MIN_MODEL_COUNT

Count = Annotated[int, Field(ge=0)]


class CostCheckStatus(StrEnum):
    """v_simulation_summary 의 cost_check_status 값. 뷰가 한국어 문구를 그대로 내보내므로 값도 같다."""

    CHECKING = "확인 중"
    UNKNOWN_INCLUDED = "미확인 포함"
    ESTIMATE_INCLUDED = "추정 포함"
    FULLY_CONFIRMED = "확정"


class SimulationSummary(BaseModel):
    """비교 실행 한 건의 요약. v_simulation_summary 한 행과 같은 칸이며 여기서 다시 계산하지 않는다.

    confirmed_cost_usd·estimated_cost_usd 가 null 이면 그 상태의 호출이 하나도 없다는 뜻이다(0 이 아님).
    비용 미확인 호출은 금액 합계에 넣지 않고 unknown_cost_count 로 센다.
    total_cost_usd 만은 뷰의 칸이 아니다. 뷰가 낸 두 합계를 더할 뿐 호출을 다시 합산하지 않는다.
    """

    simulation_id: UUID
    rerun_of_simulation_id: UUID | None
    test_type: TestType
    scenario_code: str | None
    status: SimulationStatus
    model_count: Annotated[int, Field(ge=MIN_MODEL_COUNT, le=MAX_MODEL_COUNT)]
    requested_at: AwareDatetime
    completed_at: AwareDatetime | None
    executed_by: int
    final_result_count: Count
    success_count: Count
    failure_count: Count
    confirmed_cost_usd: Money | None
    estimated_cost_usd: Money | None
    unknown_cost_count: Count
    cost_check_status: CostCheckStatus

    @computed_field
    @property
    def total_cost_usd(self) -> Money | None:
        """확정 + 추정. 금액을 아는 호출이 없으면 null 이다(0 이 아님).

        미확인 호출은 들어 있지 않다. 일부만 더한 값인지는 unknown_cost_count·cost_check_status 로 안다.
        """
        known = [
            cost
            for cost in (self.confirmed_cost_usd, self.estimated_cost_usd)
            if cost is not None
        ]
        return sum(known, Decimal(0)) if known else None


class SimulationModelResult(BaseModel):
    """모델 한 칸의 결과. 화면이 모델 칸에 그대로 그릴 수 있게 응답 원문도 함께 준다."""

    slot_no: Annotated[int, Field(ge=1, le=MAX_MODEL_COUNT)]
    request_id: UUID
    model_id: int
    # 실행 당시의 이름·상태. 현재 모델 정보와 다를 수 있다
    model_display_name_at_run: str
    model_status_at_run: ModelStatus
    execution_provider: str  # 이 칸에서 고정한 업체
    # 이 칸에 실제로 적용한 설정(실행 공통 설정과 합친 값). 과거 이력은 지금 규칙으로 다시 거절하지 않는다
    execution_config: dict[str, JsonValue]
    actual_provider: str | None  # 실제로 처리한 업체. 모르면 null
    actual_model: str | None
    status: RequestStatus
    error_type: ErrorType | None
    latency_ms: Count | None
    input_tokens: Count | None
    output_tokens: Count | None
    cost_usd: Money | None
    cost_status: CostStatus
    json_parse_status: ValidationStatus | None
    schema_validation_status: ValidationStatus | None
    missing_required_fields: list[str] | None
    comparability_note: str | None
    # 모델이 돌려준 답변. 끝나지 않았거나 실패·취소되어 답변이 없으면 null
    response_text: str | None
    # 실패한 칸에 화면이 보여 줄 문구. 내부 예외 원문이 아니라 정해진 사용자 문구다. 실패가 아니면 null
    error_message: str | None
    # IMAGE 칸은 response_text 대신 output_images 에 결과가 있다
    output_type: OutputType
    # 모델이 만든 그림(돌려준 순서). 텍스트 칸, 끝나지 않았거나 취소된 칸은 빈 목록이다
    output_images: list[OutputImageRead]

    @model_validator(mode="after")
    def _cost_unknown_means_null(self) -> Self:
        # DB 제약 ck_ai_requests_cost_unknown 과 같은 규칙. 미확인이 0 으로 나가는 것을 막는다
        if self.cost_status == CostStatus.UNKNOWN and self.cost_usd is not None:
            raise ValueError("비용 상태가 UNKNOWN 이면 cost_usd 는 null 이어야 한다")
        if self.cost_status != CostStatus.UNKNOWN and self.cost_usd is None:
            raise ValueError("비용 상태가 UNKNOWN 이 아니면 cost_usd 가 있어야 한다")
        return self


class SimulationDetailResponse(BaseModel):
    """진행·결과 조회(S-04) 응답. 완료될 때까지 화면이 같은 요청을 반복해 상태를 확인한다.

    results 에는 칸마다 마지막 시도(is_final_attempt)만 싣는다. 재시도 전 시도는 싣지 않는다.
    """

    summary: SimulationSummary
    results: Annotated[list[SimulationModelResult], Field(max_length=MAX_MODEL_COUNT)]

    @model_validator(mode="after")
    def _one_result_per_slot(self) -> Self:
        slots = [result.slot_no for result in self.results]
        if len(slots) != len(set(slots)):
            raise ValueError(
                "slot_no 가 중복되었다. 칸마다 마지막 시도 하나만 담아야 한다"
            )
        return self

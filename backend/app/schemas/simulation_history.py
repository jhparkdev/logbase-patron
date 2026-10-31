from datetime import date
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.models import ModelStatus, SimulationStatus, TestType
from app.schemas.simulation_result import SimulationSummary
from app.services.simulation_validation import MAX_MODEL_COUNT, MIN_MODEL_COUNT

# 한 번에 내려주는 이력의 상한. 정렬·페이지는 화면이 하므로 서버는 거른 결과를 통째로 준다.
# 상한을 넘으면 최신 순으로 자르고 truncated 로 알린다. 잘린 목록을 전체처럼 정렬해 보이지 않기 위해서다
MAX_HISTORY_ITEMS = 1000


class SimulationHistoryQuery(BaseModel):
    """이력 목록(S-08) 조회 조건. 화면은 이 값을 URL 검색 파라미터에 둔다.

    정렬과 페이지는 화면이 한다(팀 결정). 그 파라미터를 받는 척 무시하지 않도록 모르는 값은 거절한다.
    기간이 올바른지(시작≤종료, 366일 이내)는 오늘 날짜가 필요해 서비스가 판단한다.
    """

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None  # KST 달력 기준, 포함
    end_date: date | None = None  # KST 달력 기준, 포함
    # 검색 조건(기준서 8.3). 지정하지 않으면 거르지 않는다
    scenario_id: int | None = None
    model_id: int | None = None  # 이 모델이 참여한 실행
    status: SimulationStatus | None = None
    simulation_id: UUID | None = None


class SimulationHistoryList(BaseModel):
    """이력 목록 응답. 요청 시각 최신 순(같으면 실행 ID 내림차순)으로 준다.

    항목은 진행·결과 조회의 요약과 같은 모양이라 합계 계산을 한 곳(뷰)에서만 한다.
    total 은 조건에 맞는 전체 건수, truncated 는 상한 때문에 items 가 전체보다 적은지다.
    """

    items: list[SimulationSummary]
    total: Annotated[int, Field(ge=0)]
    truncated: bool

    @model_validator(mode="after")
    def _truncated_matches_count(self) -> Self:
        if self.truncated != (self.total > len(self.items)):
            raise ValueError("truncated 는 total 이 items 보다 많을 때만 true 다")
        return self


class RerunRoutingPolicy(BaseModel):
    """재실행 초안에 돌려주는 Provider 정책. 사용자가 고칠 값만 담는다.

    과거 기록에는 서버가 적어 둔 값(require_parameters 등)이 더 들어 있으므로
    모르는 키는 거절하지 않고 버린다(pydantic 기본 동작).
    """

    allow_fallbacks: bool


class RerunBlockReason(StrEnum):
    """재실행을 시작할 수 없는 사유. 모델 상태는 사유가 아니다(교체·제외하면 되므로)."""

    INPUT_MISSING = "INPUT_MISSING"  # 저장된 입력을 복원할 수 없다


class RerunModel(BaseModel):
    """재실행 초안의 모델 한 칸. 과거에 고른 값에 모델의 현재 상태를 더해 교체·제외 안내를 돕는다."""

    # 과거에 고른 값. 새 실행 요청의 모델 칸과 같은 이름이다
    model_id: int
    execution_provider: str
    # 현재 값. 실행 당시 이름·상태(결과 조회 응답)와 다를 수 있다
    current_display_name: str
    current_status: ModelStatus
    # 지금 일반 실행에서 고를 수 있는가. 판단은 is_model_selectable 이 한다
    selectable: bool


class SimulationRerunDraft(BaseModel):
    """재실행 초안(S-09) 응답. 과거 실행의 입력값을 그대로 돌려주어 화면 입력칸을 채운다.

    입력 필드는 비교 실행 요청(SimulationCreateRequest)과 같고, 화면이 안내에 쓰는
    rerunnable·blocked_reason 과 모델 칸의 현재 상태가 더해진다. 사용자가 고친 값은
    그 둘을 뺀 채 새 실행 요청으로 보낸다(rerun_of_simulation_id 는 그대로 보낸다).
    과거 이력은 지금 규칙으로 다시 거절하지 않는다. 새 실행 요청이 들어올 때 검증한다.
    """

    rerun_of_simulation_id: UUID
    test_type: TestType
    scenario_id: int | None
    prompt_text: str  # 실행 당시 원문 그대로
    input_text: str | None
    json_schema: dict[str, JsonValue] | None
    execution_config: dict[str, JsonValue]
    routing_policy: RerunRoutingPolicy
    models: Annotated[
        list[RerunModel],
        Field(min_length=MIN_MODEL_COUNT, max_length=MAX_MODEL_COUNT),
    ]
    rerunnable: bool
    blocked_reason: RerunBlockReason | None

    @model_validator(mode="after")
    def _reason_matches_rerunnable(self) -> Self:
        if self.rerunnable and self.blocked_reason is not None:
            raise ValueError("재실행할 수 있으면 blocked_reason 은 null 이어야 한다")
        if not self.rerunnable and self.blocked_reason is None:
            raise ValueError("재실행할 수 없으면 blocked_reason 이 있어야 한다")
        return self

from datetime import date
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.models import ModelStatus, SimulationStatus, TestType
from app.schemas.simulation_result import SimulationSummary
from app.schemas.simulation_types import Page
from app.services.simulation_sort import (
    DEFAULT_SORT_COLUMN,
    DEFAULT_SORT_DIRECTION,
    SortColumn,
    SortDirection,
)
from app.services.simulation_validation import MAX_MODEL_COUNT, MIN_MODEL_COUNT

DEFAULT_PAGE_SIZE = 10  # 시뮬레이터 이력 화면 목업의 "10개씩 보기"
MAX_PAGE_SIZE = 100


class SimulationHistoryQuery(BaseModel):
    """이력 목록(S-08) 조회 조건. 화면은 이 값을 URL 검색 파라미터에 둔다.

    기간이 올바른지(시작≤종료, 366일 이내)는 오늘 날짜가 필요해 resolve_period 가 판단한다.
    둘 다 없으면 서비스가 최근 30일을 쓴다.
    """

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None  # KST 달력 기준, 포함
    end_date: date | None = None  # KST 달력 기준, 포함
    # 검색 조건(기준서 8.3). 지정하지 않으면 거르지 않는다
    scenario_id: int | None = None
    model_id: int | None = None  # 이 모델이 참여한 실행
    status: SimulationStatus | None = None
    simulation_id: UUID | None = None
    # 타입이 허용 목록이다. 목록 밖의 값은 거절하고 OpenAPI enum 으로 프론트엔드에 전달된다
    sort: SortColumn = DEFAULT_SORT_COLUMN
    direction: SortDirection = DEFAULT_SORT_DIRECTION
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE


SimulationHistoryPage = Page[SimulationSummary]
"""이력 목록 응답. 항목은 진행·결과 조회의 요약과 같은 모양이라 합계 계산을 한 곳(뷰)에서만 한다."""


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

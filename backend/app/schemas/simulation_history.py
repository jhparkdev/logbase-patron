from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.models import TestType
from app.schemas.common import Page
from app.schemas.simulation import ModelSelectionRequest, RoutingPolicy
from app.schemas.simulation_result import SimulationSummary
from app.services.simulation_sort import (
    DEFAULT_SORT_COLUMN,
    DEFAULT_SORT_DIRECTION,
    SortColumn,
    SortDirection,
)
from app.services.simulation_validation import MAX_MODEL_COUNT, MIN_MODEL_COUNT

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class SimulationHistoryQuery(BaseModel):
    """이력 목록(S-08) 조회 조건. 화면은 이 값을 URL 검색 파라미터에 둔다.

    기간이 올바른지(시작≤종료, 366일 이내)는 오늘 날짜가 필요해 resolve_period 가 판단한다.
    둘 다 없으면 서비스가 최근 30일을 쓴다.
    """

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None  # KST 달력 기준, 포함
    end_date: date | None = None  # KST 달력 기준, 포함
    # 타입이 허용 목록이다. 목록 밖의 값은 거절하고 OpenAPI enum 으로 프론트엔드에 전달된다
    sort: SortColumn = DEFAULT_SORT_COLUMN
    direction: SortDirection = DEFAULT_SORT_DIRECTION
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE


SimulationHistoryPage = Page[SimulationSummary]
"""이력 목록 응답. 항목은 진행·결과 조회의 요약과 같은 모양이라 합계 계산을 한 곳(뷰)에서만 한다."""


class SimulationRerunDraft(BaseModel):
    """재실행 초안(S-09) 응답. 과거 실행의 입력값을 그대로 돌려주어 화면 입력칸을 채운다.

    비교 실행 요청(SimulationCreateRequest)과 입력 필드가 같아서, 사용자가 고친 값을
    rerun_of_simulation_id 를 뺀 채 그대로 새 실행 요청으로 보낼 수 있다.
    과거 이력은 지금 규칙으로 다시 거절하지 않는다. 새 실행 요청이 들어올 때 검증한다.
    """

    rerun_of_simulation_id: UUID
    test_type: TestType
    scenario_id: int | None
    prompt_text: str  # 실행 당시 원문 그대로
    input_text: str | None
    json_schema: dict[str, JsonValue] | None
    execution_config: dict[str, JsonValue]
    routing_policy: RoutingPolicy
    models: Annotated[
        list[ModelSelectionRequest],
        Field(min_length=MIN_MODEL_COUNT, max_length=MAX_MODEL_COUNT),
    ]

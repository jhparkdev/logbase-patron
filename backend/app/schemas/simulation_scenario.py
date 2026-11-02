from pydantic import BaseModel, ConfigDict, JsonValue

from app.models import InputType


class ScenarioListQuery(BaseModel):
    """시나리오 목록 조건. 새 실행은 활성만 고르고, 이력 필터는 비활성도 고를 수 있어야 한다."""

    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False


class ScenarioRead(BaseModel):
    """시나리오 하나. 실행 때 합칠 기본값을 화면이 미리 채우도록 그대로 준다."""

    model_config = ConfigDict(from_attributes=True)

    scenario_id: int
    scenario_code: str
    name: str
    description: str | None
    input_type: InputType
    prompt_template: str
    default_json_schema: dict[str, JsonValue] | None
    # 저장된 값을 지금 규칙으로 거절하면 목록 전체를 못 쓰게 되므로 dict 로 준다. 검증은 실행 요청 때 한다
    default_execution_config: dict[str, JsonValue]
    is_active: bool


class ScenarioList(BaseModel):
    """시나리오 전체 목록. 건수가 적은 관리 데이터라 페이지를 나누지 않는다."""

    items: list[ScenarioRead]

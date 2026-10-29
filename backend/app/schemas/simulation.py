from typing import Annotated, Self
from uuid import UUID

from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from app.models import TestType

# 모델 선택 규칙은 services 의 순수 검증 모듈에 한 번만 정의하고 여기서는 가져다 쓴다.
# 그 모듈이 schemas 를 가져오게 만들면 순환 import 가 되므로 그러지 않는다.
from app.services.simulation_validation import (
    MAX_MODEL_COUNT,
    MIN_MODEL_COUNT,
    ModelSelection,
    validate_model_selection,
)


class ModelSelectionRequest(BaseModel):
    """비교 실행에서 고른 모델 한 칸. 필드 이름은 simulation_results 컬럼과 같다."""

    model_id: int  # models 표의 model_id
    # 실행 Provider. 자동 라우팅이 없으므로 서버 업체가 하나뿐인 모델도 반드시 적는다
    execution_provider: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ]


def _reject_invalid_selection(
    selections: list[ModelSelectionRequest],
) -> list[ModelSelectionRequest]:
    # 같은 모델 + 같은 Provider 중복을 막는다. 오류는 ValueError 라서 pydantic 이 422 로 바꾼다
    validate_model_selection(
        [ModelSelection(s.model_id, s.execution_provider) for s in selections]
    )
    return selections


ModelSelections = Annotated[
    list[ModelSelectionRequest],
    # min_length/max_length 는 OpenAPI 의 minItems/maxItems 로 프론트엔드에 전달된다
    Field(min_length=MIN_MODEL_COUNT, max_length=MAX_MODEL_COUNT),
    AfterValidator(_reject_invalid_selection),
]
"""비교 실행에서 고른 모델 2~4개. 같은 모델은 Provider 가 다를 때만 두 번 넣을 수 있다."""


def _reject_invalid_json_schema(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    # 모델 호출 비용이 나간 뒤에야 Schema 오류를 알게 되지 않도록 요청 단계에서 확인한다
    try:
        validator_for(schema).check_schema(schema)
    except SchemaError as error:
        raise ValueError(f"JSON Schema 가 올바르지 않다: {error.message}") from error
    return schema


JsonSchemaDocument = Annotated[
    dict[str, JsonValue], AfterValidator(_reject_invalid_json_schema)
]


class RoutingPolicy(BaseModel):
    """사용자가 정하는 Provider 정책. 키 이름은 simulation_runs.routing_policy 에 저장되는 값과 같다.

    업체 순서(order)는 모델 칸마다 execution_provider 로 정해지므로 여기에는 없다.
    require_parameters(요청한 설정을 모두 지원하는 업체만 사용)는 비교 실행의 고정 조건이라
    사용자가 정하지 않는다. 서버가 항상 켜서 호출하고 저장할 때 함께 기록한다.
    """

    model_config = ConfigDict(extra="forbid")

    # 비교 조건이 바뀌지 않도록 선택한 업체가 안 될 때 다른 업체로 넘어가지 않는다
    allow_fallbacks: bool = False


class SimulationCreateRequest(BaseModel):
    """비교 실행 요청. simulation_runs 한 행을 만들 재료 중 사용자가 정하는 값만 담는다.

    project_id·key_id·executed_by 는 서버가 로그인 세션과 PoC Key 로 정하고,
    model_count·input_hash·status·시각은 서버가 계산하므로 받지 않는다(extra 는 거절).
    """

    model_config = ConfigDict(extra="forbid")

    test_type: TestType
    # 재실행이면 원본 실행의 ID. 원본이 실제로 있는지는 DB 가 필요해 서비스가 확인한다
    rerun_of_simulation_id: UUID | None = None
    scenario_id: int | None = None  # test_scenarios 표의 scenario_id
    # 실행 당시 원문이라 다듬지 않는다. 공백뿐인 값만 거절한다(\S = 공백이 아닌 글자 하나 이상)
    prompt_text: Annotated[str, Field(pattern=r"\S")]
    input_text: str | None = None
    json_schema: JsonSchemaDocument | None = None  # 없으면 Schema 검증은 "미적용"
    execution_config: dict[str, JsonValue] = Field(default_factory=dict)
    routing_policy: RoutingPolicy = Field(default_factory=RoutingPolicy)
    models: ModelSelections

    @model_validator(mode="after")
    def _scenario_matches_test_type(self) -> Self:
        # DB 제약 ck_simulation_runs_scenario 와 같은 규칙. 위반이 DB 오류(500)가 되지 않게 먼저 막는다
        if self.test_type == TestType.SCENARIO and self.scenario_id is None:
            raise ValueError("시나리오 실행에는 scenario_id 가 필요하다")
        if self.test_type == TestType.CUSTOM and self.scenario_id is not None:
            raise ValueError("직접 작성 실행에는 scenario_id 를 보낼 수 없다")
        return self

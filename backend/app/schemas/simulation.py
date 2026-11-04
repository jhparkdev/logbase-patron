from enum import StrEnum
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
from app.schemas.simulation_image import MAX_IMAGE_COUNT
from app.schemas.simulation_output import ImageConfig, OutputType

# 모델 선택 규칙은 services 의 순수 검증 모듈에 한 번만 정의하고 여기서는 가져다 쓴다.
# 그 모듈이 schemas 를 가져오게 만들면 순환 import 가 되므로 그러지 않는다.
from app.services.simulation_validation import MAX_MODEL_COUNT, MIN_MODEL_COUNT


class ReasoningEffort(StrEnum):
    """추론 강도. OpenRouter 의 reasoning.effort 값이다. 모델마다 지원하는 값이 달라 지원하지 않는 값은 OpenRouter 가 처리한다."""

    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


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
    사용자가 정하지 않는다. 서버가 정해서 호출하고, 실제로 보낸 값을 저장할 때 함께 기록한다.
    """

    model_config = ConfigDict(extra="forbid")

    # 비교 조건이 바뀌지 않도록 선택한 업체가 안 될 때 다른 업체로 넘어가지 않는다
    allow_fallbacks: bool = False


# 시나리오 기본값(seed)이 512~1024 라서 여유를 두고 정한 상한이다. 한 번의 실수로 큰 비용이 나가지 않게 한다
MAX_TOKENS_LIMIT = 4096
# Prompt·입력 텍스트 한 칸의 최대 글자 수. 화면과 같은 값이며 OpenAPI maxLength 로 화면에 전달된다
MAX_TEXT_LENGTH = 2_000
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0

Temperature = Annotated[
    float, Field(ge=MIN_TEMPERATURE, le=MAX_TEMPERATURE, allow_inf_nan=False)
]
# strict: 512.5 나 "512" 처럼 정수가 아닌 값은 변환하지 않고 거절한다
MaxTokens = Annotated[int, Field(strict=True, ge=1, le=MAX_TOKENS_LIMIT)]


class ExecutionConfig(BaseModel):
    """모델 실행 설정. 시나리오 기본 실행 설정(test_scenarios.default_execution_config)과 같은 항목이다.

    허용 항목만 받는다. provider·response_format 같은 키가 섞여 업체 고정이나 Schema 전달을
    덮어쓰는 일을 막기 위해서다. 보내지 않은 항목은 모델 기본값(또는 시나리오 기본값)을 쓴다.
    """

    model_config = ConfigDict(extra="forbid")

    temperature: Temperature | None = None
    max_tokens: MaxTokens | None = None
    reasoning_effort: ReasoningEffort | None = None


class ModelSelectionRequest(BaseModel):
    """비교 실행에서 고른 모델 한 칸. 필드 이름은 simulation_results 컬럼과 같다."""

    model_id: int  # models 표의 model_id
    # 실행 Provider. 자동 라우팅이 없으므로 서버 업체가 하나뿐인 모델도 반드시 적는다
    execution_provider: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ]
    # 이 칸에만 적용할 설정. 정하지 않은 항목은 실행 공통 설정을 따르고,
    # 공통 설정이 꺼져 있으면 모델 기본값을 쓴다
    execution_config: ExecutionConfig = Field(default_factory=ExecutionConfig)


ModelSelections = Annotated[
    list[ModelSelectionRequest],
    # min_length/max_length 는 OpenAPI 의 minItems/maxItems 로 프론트엔드에 전달된다
    Field(min_length=MIN_MODEL_COUNT, max_length=MAX_MODEL_COUNT),
]
"""비교 실행에서 고른 모델 2~4개. 같은 모델·Provider 중복은 적용 설정까지 합친 뒤 접수 서비스가 판단한다."""


class SimulationCreateRequest(BaseModel):
    """비교 실행 요청. simulation_runs 한 행을 만들 재료 중 사용자가 정하는 값만 담는다.

    project_id·key_id·executed_by 는 서버가 PoC Key 와 실행자 계정(app/api/deps.py)으로 정하고,
    model_count·input_hash·status·시각은 서버가 계산하므로 받지 않는다(extra 는 거절).
    """

    model_config = ConfigDict(extra="forbid")

    test_type: TestType
    # 재실행이면 원본 실행의 ID. 원본이 실제로 있는지는 DB 가 필요해 서비스가 확인한다
    rerun_of_simulation_id: UUID | None = None
    scenario_id: int | None = None  # test_scenarios 표의 scenario_id
    # 실행 당시 원문이라 다듬지 않는다. 공백뿐인 값만 거절한다(\S = 공백이 아닌 글자 하나 이상)
    prompt_text: Annotated[str, Field(pattern=r"\S", max_length=MAX_TEXT_LENGTH)]
    input_text: Annotated[str, Field(max_length=MAX_TEXT_LENGTH)] | None = None
    json_schema: JsonSchemaDocument | None = None  # 없으면 Schema 검증은 "미적용"
    # 실행 공통 설정. null 이면 공통 설정을 끈 것이라 시나리오 기본값도 쓰지 않고,
    # 칸마다 정한 값만 보낸다. 보내지 않으면 빈 공통 설정(켬)으로 본다
    execution_config: ExecutionConfig | None = Field(default_factory=ExecutionConfig)
    routing_policy: RoutingPolicy = Field(default_factory=RoutingPolicy)
    models: ModelSelections
    # 먼저 올려 둔 이미지(POST /simulations/images 의 asset_id). 순서가 곧 모델에 보내는 순서다.
    # 올린 적 없는 ID 인지는 DB 가 필요해 서비스가 확인한다
    asset_ids: Annotated[list[UUID], Field(max_length=MAX_IMAGE_COUNT)] = Field(
        default_factory=list
    )
    # IMAGE 면 모든 칸이 OpenRouter 이미지 생성(/images)으로 호출되고, 올린 이미지는 참고 이미지가 된다
    output_type: OutputType = OutputType.TEXT
    image_config: ImageConfig | None = None  # IMAGE 실행에만 보낸다

    @model_validator(mode="after")
    def _settings_match_output_type(self) -> Self:
        # 이미지 호출은 텍스트 설정과 Schema 를 보내지 않는다. 받아 두면 기록과 실제 호출이 달라진다
        if self.output_type == OutputType.TEXT:
            if self.image_config is not None:
                raise ValueError("이미지 옵션은 이미지 생성 실행에만 보낼 수 있다")
            return self
        if self.json_schema is not None:
            raise ValueError("이미지 생성 실행에는 JSON Schema 를 보낼 수 없다")
        configs = [self.execution_config, *(m.execution_config for m in self.models)]
        if any(
            config.model_dump(exclude_none=True)
            for config in configs
            if config is not None
        ):
            raise ValueError("이미지 생성 실행에는 텍스트 실행 설정을 보낼 수 없다")
        return self

    @model_validator(mode="after")
    def _no_image_twice(self) -> Self:
        # 같은 이미지를 두 번 보내면 모델이 두 장으로 읽고 비용도 두 번 나간다
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("같은 이미지를 두 번 보낼 수 없다")
        return self

    @model_validator(mode="after")
    def _scenario_matches_test_type(self) -> Self:
        # DB 제약 ck_simulation_runs_scenario 와 같은 규칙. 위반이 DB 오류(500)가 되지 않게 먼저 막는다
        if self.test_type == TestType.SCENARIO and self.scenario_id is None:
            raise ValueError("시나리오 실행에는 scenario_id 가 필요하다")
        if self.test_type == TestType.CUSTOM and self.scenario_id is not None:
            raise ValueError("직접 작성 실행에는 scenario_id 를 보낼 수 없다")
        return self


class SimulationAccepted(BaseModel):
    """실행 요청을 받았다는 응답(202). 진행과 결과는 이 ID 로 조회한다."""

    simulation_id: UUID

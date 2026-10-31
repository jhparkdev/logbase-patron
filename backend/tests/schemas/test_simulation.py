import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.models import (
    TestType as RunType,
)  # 이름이 Test 로 시작하면 pytest 가 테스트로 오해한다
from app.schemas.simulation import (
    MAX_TEMPERATURE,
    MAX_TEXT_LENGTH,
    MAX_TOKENS_LIMIT,
    MIN_TEMPERATURE,
    ModelSelectionRequest,
    ModelSelections,
    ReasoningEffort,
    SimulationCreateRequest,
)

# models 표의 model_id(숫자)
GPT = 1
CLAUDE = 2
GEMINI = 3
MISTRAL = 4
LLAMA = 5

PROVIDER_A = "DeepInfra"
PROVIDER_B = "DekaLLM"


class Request(BaseModel):
    """ModelSelections 를 필드로 쓰는 최소 모델. 비교 실행 요청이 이렇게 쓴다."""

    models: ModelSelections


def selection(model_id: int, provider: str = PROVIDER_A) -> dict[str, object]:
    return {"model_id": model_id, "execution_provider": provider}


def test_selection_has_model_id_and_provider() -> None:
    chosen = ModelSelectionRequest(model_id=GPT, execution_provider=PROVIDER_A)

    # 칸에서 설정을 정하지 않았으면 실행 공통 설정을 쓴다는 뜻으로 비워 둔다
    assert chosen.model_dump(exclude_none=True) == {
        "model_id": GPT,
        "execution_provider": PROVIDER_A,
        "execution_config": {},
    }


def test_provider_is_required() -> None:
    # simulation_results.execution_provider 는 NOT NULL 이다 (자동 라우팅 없음)
    with pytest.raises(ValidationError):
        ModelSelectionRequest(model_id=GPT)  # type: ignore[call-arg]


@pytest.mark.parametrize("provider", ["", "   "])
def test_blank_provider_is_rejected(provider: str) -> None:
    with pytest.raises(ValidationError):
        ModelSelectionRequest(model_id=GPT, execution_provider=provider)


def test_model_id_must_be_a_number() -> None:
    with pytest.raises(ValidationError):
        ModelSelectionRequest(model_id="gpt", execution_provider=PROVIDER_A)


# 개수 경계값은 바로 전, 정확히 그 값, 바로 후를 모두 검사한다 (T-19)
@pytest.mark.parametrize("count", [2, 3, 4])
def test_two_to_four_models_are_accepted(count: int) -> None:
    models = [selection(model_id) for model_id in range(1, count + 1)]

    assert len(Request(models=models).models) == count


@pytest.mark.parametrize("count", [0, 1, 5])
def test_fewer_than_two_or_more_than_four_are_rejected(count: int) -> None:
    models = [selection(model_id) for model_id in range(1, count + 1)]

    with pytest.raises(ValidationError):
        Request(models=models)


def test_same_model_with_a_different_provider_is_allowed() -> None:
    # 같은 모델도 Provider 가 다르면 두 칸에 넣어 비교할 수 있다
    models = [selection(GPT, PROVIDER_A), selection(GPT, PROVIDER_B)]

    assert len(Request(models=models).models) == 2


def test_same_model_with_the_same_provider_passes_the_schema() -> None:
    # 설정까지 같은지는 실행 공통 설정·시나리오 기본값과 합친 뒤에야 알 수 있어 접수 서비스가 판단한다
    models = [selection(GPT, PROVIDER_A), selection(GPT, PROVIDER_A)]

    assert len(Request(models=models).models) == 2


def test_different_models_with_the_same_provider_are_allowed() -> None:
    models = [selection(GPT, PROVIDER_A), selection(CLAUDE, PROVIDER_A)]

    assert len(Request(models=models).models) == 2


def test_openapi_carries_the_model_count_limits() -> None:
    # 프론트엔드는 한도를 따로 외우지 않고 OpenAPI 문서에서 받는다
    schema = TypeAdapter(ModelSelections).json_schema()

    assert (schema["minItems"], schema["maxItems"]) == (2, 4)


SCENARIO_ID = 7
PROMPT = "상품 설명을 써 주세요"


def create_body(**overrides: object) -> dict[str, object]:
    """직접 작성(CUSTOM) 실행의 최소 요청. 필요한 값만 덮어써서 쓴다."""
    body: dict[str, object] = {
        "test_type": "CUSTOM",
        "prompt_text": PROMPT,
        "models": [selection(GPT), selection(CLAUDE)],
    }
    body.update(overrides)
    return body


def test_minimal_custom_request_gets_safe_defaults() -> None:
    request = SimulationCreateRequest(**create_body())

    assert request.test_type == RunType.CUSTOM
    assert request.scenario_id is None
    assert request.input_text is None
    assert request.json_schema is None
    assert request.execution_config.model_dump(exclude_none=True) == {}
    # 비교 실행은 Fallback 을 끄는 것이 기본이다 (기준서 7.3 Benchmark 원칙)
    assert request.routing_policy.model_dump() == {"allow_fallbacks": False}


def test_scenario_request_with_scenario_id_is_accepted() -> None:
    request = SimulationCreateRequest(
        **create_body(test_type="SCENARIO", scenario_id=SCENARIO_ID)
    )

    assert request.scenario_id == SCENARIO_ID


# DB 제약 ck_simulation_runs_scenario 와 같은 규칙을 입력 단계에서 먼저 막는다
def test_scenario_request_without_scenario_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="scenario_id"):
        SimulationCreateRequest(**create_body(test_type="SCENARIO"))


def test_custom_request_with_scenario_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="scenario_id"):
        SimulationCreateRequest(**create_body(scenario_id=SCENARIO_ID))


def test_unknown_test_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(test_type="RANDOM"))


def test_prompt_is_required() -> None:
    body = create_body()
    del body["prompt_text"]

    with pytest.raises(ValidationError):
        SimulationCreateRequest(**body)


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_blank_prompt_is_rejected(prompt: str) -> None:
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(prompt_text=prompt))


def test_text_limit_is_two_thousand_characters() -> None:
    assert MAX_TEXT_LENGTH == 2_000


@pytest.mark.parametrize("field", ["prompt_text", "input_text"])
@pytest.mark.parametrize(
    ("length", "accepted"),
    [
        (MAX_TEXT_LENGTH - 1, True),
        (MAX_TEXT_LENGTH, True),
        (MAX_TEXT_LENGTH + 1, False),
    ],
    ids=["just-under", "exactly", "just-over"],
)
def test_prompt_and_input_text_are_limited(
    field: str, length: int, accepted: bool
) -> None:
    # 화면과 같은 한도를 서버 계약에 둔다. 한글도 한 글자로 센다
    body = create_body(**{field: "가" * length})

    if accepted:
        assert len(getattr(SimulationCreateRequest(**body), field)) == length
    else:
        with pytest.raises(ValidationError):
            SimulationCreateRequest(**body)


def test_openapi_carries_the_text_limit() -> None:
    properties = SimulationCreateRequest.model_json_schema()["properties"]

    assert properties["prompt_text"]["maxLength"] == MAX_TEXT_LENGTH
    input_text = next(
        option for option in properties["input_text"]["anyOf"] if "type" in option
    )
    assert input_text["maxLength"] == MAX_TEXT_LENGTH


def test_prompt_is_kept_exactly_as_typed() -> None:
    # simulation_runs.prompt_text 는 실행 당시 원문이라 앞뒤 공백·줄바꿈을 다듬지 않는다
    prompt = "  첫 줄\n둘째 줄\n"

    assert (
        SimulationCreateRequest(**create_body(prompt_text=prompt)).prompt_text == prompt
    )


def test_model_count_rule_applies_to_the_whole_request() -> None:
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(models=[selection(GPT)]))


# 비용 귀속·상태·계산값은 서버가 정한다. 클라이언트가 보내면 조용히 무시하지 않고 거절한다
@pytest.mark.parametrize(
    "field, value",
    [
        ("project_id", 1),
        ("key_id", 1),
        ("executed_by", 1),
        ("status", "SUCCESS"),
        ("model_count", 3),
        ("input_hash", "0" * 64),
        ("data_source", "MOCK"),
    ],
)
def test_server_owned_fields_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match=field):
        SimulationCreateRequest(**create_body(**{field: value}))


def test_valid_json_schema_is_accepted() -> None:
    schema = {"type": "object", "required": ["title"]}

    assert (
        SimulationCreateRequest(**create_body(json_schema=schema)).json_schema == schema
    )


def test_broken_json_schema_is_rejected_before_any_model_is_called() -> None:
    # 모델 호출 비용이 나간 뒤에야 Schema 오류를 알게 되지 않도록 입구에서 막는다
    with pytest.raises(ValidationError, match="JSON Schema"):
        SimulationCreateRequest(**create_body(json_schema={"type": "nonsense"}))


def execution_config_of(config: dict[str, object]) -> dict[str, object]:
    """요청에 담긴 실행 설정이 저장될 때의 모양. 보내지 않은 항목은 들어가지 않는다."""
    request = SimulationCreateRequest(**create_body(execution_config=config))
    return request.execution_config.model_dump(exclude_none=True)


def test_execution_config_accepts_the_scenario_defaults_shape() -> None:
    # 시나리오 기본 실행 설정(seed)과 같은 모양이다
    config = {"temperature": 0.7, "max_tokens": 1024}

    assert execution_config_of(config) == config


def test_each_execution_setting_is_optional() -> None:
    assert execution_config_of({"temperature": 0}) == {"temperature": 0}
    assert execution_config_of({"max_tokens": 512}) == {"max_tokens": 512}


# 값 범위는 바로 전, 정확히 그 값, 바로 후를 모두 검사한다
@pytest.mark.parametrize("temperature", [MIN_TEMPERATURE, 1, MAX_TEMPERATURE])
def test_temperature_within_range_is_accepted(temperature: float) -> None:
    assert execution_config_of({"temperature": temperature})["temperature"] == (
        temperature
    )


@pytest.mark.parametrize(
    "temperature", [MIN_TEMPERATURE - 0.01, MAX_TEMPERATURE + 0.01, float("nan")]
)
def test_temperature_outside_range_is_rejected(temperature: float) -> None:
    with pytest.raises(ValidationError):
        execution_config_of({"temperature": temperature})


@pytest.mark.parametrize("max_tokens", [1, 2, MAX_TOKENS_LIMIT - 1, MAX_TOKENS_LIMIT])
def test_max_tokens_within_range_is_accepted(max_tokens: int) -> None:
    assert execution_config_of({"max_tokens": max_tokens}) == {"max_tokens": max_tokens}


@pytest.mark.parametrize("max_tokens", [0, -1, MAX_TOKENS_LIMIT + 1])
def test_max_tokens_outside_range_is_rejected(max_tokens: int) -> None:
    # 상한이 없으면 한 번의 실수로 큰 비용이 나갈 수 있다
    with pytest.raises(ValidationError):
        execution_config_of({"max_tokens": max_tokens})


@pytest.mark.parametrize("max_tokens", [512.5, "512", True])
def test_max_tokens_must_be_a_whole_number(max_tokens: object) -> None:
    with pytest.raises(ValidationError):
        execution_config_of({"max_tokens": max_tokens})


@pytest.mark.parametrize(
    "key", ["provider", "response_format", "model", "stream", "stop", "top_p"]
)
def test_execution_config_rejects_keys_outside_the_allow_list(key: str) -> None:
    # provider·response_format 이 섞이면 업체 고정이나 Schema 전달을 덮어쓸 수 있다
    with pytest.raises(ValidationError, match=key):
        execution_config_of({key: 1})


def test_openapi_carries_the_execution_setting_limits() -> None:
    schema = SimulationCreateRequest.model_json_schema()["$defs"]["ExecutionConfig"]

    assert schema["additionalProperties"] is False
    assert schema["properties"]["max_tokens"]["anyOf"][0]["maximum"] == MAX_TOKENS_LIMIT


def test_fallback_can_be_switched_on_or_off() -> None:
    for value in (True, False):
        request = SimulationCreateRequest(
            **create_body(routing_policy={"allow_fallbacks": value})
        )
        assert request.routing_policy.allow_fallbacks is value


def test_require_parameters_is_decided_by_the_server_not_the_client() -> None:
    # 요청한 설정을 모두 지원하는 업체만 쓰는 것은 비교 실행의 고정 조건이라 사용자가 끌 수 없다.
    # 서버가 정해서 호출하고, 실제로 보낸 값을 기록한다
    with pytest.raises(ValidationError, match="require_parameters"):
        SimulationCreateRequest(
            **create_body(routing_policy={"require_parameters": False})
        )


def test_routing_policy_rejects_unknown_keys() -> None:
    # order(업체 순서)는 모델 칸마다 execution_provider 로 정해지므로 실행 전체 정책에는 없다
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(routing_policy={"order": ["DeepInfra"]}))


PAST_RUN_ID = "0192a3c4-0000-7000-8000-000000000001"


def test_request_is_not_a_rerun_by_default() -> None:
    assert SimulationCreateRequest(**create_body()).rerun_of_simulation_id is None


def test_rerun_request_names_the_original_run() -> None:
    request = SimulationCreateRequest(**create_body(rerun_of_simulation_id=PAST_RUN_ID))

    assert str(request.rerun_of_simulation_id) == PAST_RUN_ID


@pytest.mark.parametrize("value", ["", "not-a-uuid", 12345])
def test_rerun_of_must_be_a_run_id(value: object) -> None:
    # 번호 형식이 틀린 값이 DB 까지 가서 500 이 되지 않도록 입구에서 막는다
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(rerun_of_simulation_id=value))


def test_openapi_lists_test_type_values_and_forbids_extra_fields() -> None:
    # 프론트엔드는 test_type 값을 따로 외우지 않고 OpenAPI 문서에서 받는다
    schema = SimulationCreateRequest.model_json_schema()

    assert schema["properties"]["test_type"]["$ref"].endswith("TestType")
    assert schema["$defs"]["TestType"]["enum"] == ["SCENARIO", "CUSTOM"]
    assert schema["additionalProperties"] is False


# --- 모델별 실행 설정 ---
def slot_config_of(config: dict[str, object]) -> dict[str, object]:
    chosen = ModelSelectionRequest(
        model_id=GPT, execution_provider=PROVIDER_A, execution_config=config
    )
    return chosen.execution_config.model_dump(exclude_none=True)


def test_a_slot_can_set_effort_temperature_and_max_tokens() -> None:
    config = {"reasoning_effort": "high", "temperature": 0.2, "max_tokens": 2048}

    assert slot_config_of(config) == config


def test_the_run_level_config_accepts_reasoning_effort_too() -> None:
    assert execution_config_of({"reasoning_effort": "low"}) == {
        "reasoning_effort": "low"
    }


@pytest.mark.parametrize(
    "effort", ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
)
def test_documented_reasoning_efforts_are_accepted(effort: str) -> None:
    assert slot_config_of({"reasoning_effort": effort}) == {"reasoning_effort": effort}


@pytest.mark.parametrize("effort", ["", "HIGH", "extreme", 3, True])
def test_other_reasoning_efforts_are_rejected(effort: object) -> None:
    with pytest.raises(ValidationError):
        slot_config_of({"reasoning_effort": effort})


def test_slot_settings_have_the_same_ranges_as_the_run_settings() -> None:
    with pytest.raises(ValidationError):
        slot_config_of({"temperature": MAX_TEMPERATURE + 0.01})
    with pytest.raises(ValidationError):
        slot_config_of({"max_tokens": MAX_TOKENS_LIMIT + 1})


def test_a_slot_rejects_keys_outside_the_allow_list() -> None:
    with pytest.raises(ValidationError):
        slot_config_of({"provider": {"order": ["x"]}})


def test_openapi_lists_the_reasoning_effort_values() -> None:
    # 허용 값은 OpenAPI enum 으로 프론트엔드에 전달한다
    schema = SimulationCreateRequest.model_json_schema()["$defs"]["ExecutionConfig"]
    options = schema["properties"]["reasoning_effort"]["anyOf"][0]
    effort_enum = schema_ref(options)

    assert effort_enum["enum"] == list(ReasoningEffort)


def schema_ref(options: dict[str, object]) -> dict[str, object]:
    name = str(options["$ref"]).rsplit("/", 1)[-1]
    defs = SimulationCreateRequest.model_json_schema()["$defs"]
    return defs[name]

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.models import (
    TestType as RunType,
)  # 이름이 Test 로 시작하면 pytest 가 테스트로 오해한다
from app.schemas.simulation import (
    ModelSelectionRequest,
    ModelSelections,
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

    assert chosen.model_dump() == {"model_id": GPT, "execution_provider": PROVIDER_A}


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


def test_same_model_with_the_same_provider_is_rejected() -> None:
    models = [selection(GPT, PROVIDER_A), selection(CLAUDE), selection(GPT, PROVIDER_A)]

    with pytest.raises(ValidationError, match="중복"):
        Request(models=models)


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
    assert request.execution_config == {}
    # 비교 실행은 Fallback 을 끄고 요청 파라미터를 모두 지원하는 업체만 쓰는 것이 기본이다
    assert request.routing_policy.model_dump() == {
        "allow_fallbacks": False,
        "require_parameters": True,
    }


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


def test_prompt_is_kept_exactly_as_typed() -> None:
    # simulation_runs.prompt_text 는 실행 당시 원문이라 앞뒤 공백·줄바꿈을 다듬지 않는다
    prompt = "  첫 줄\n둘째 줄\n"

    assert (
        SimulationCreateRequest(**create_body(prompt_text=prompt)).prompt_text == prompt
    )


def test_model_selection_rules_apply_to_the_whole_request() -> None:
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(models=[selection(GPT)]))
    with pytest.raises(ValidationError, match="중복"):
        SimulationCreateRequest(**create_body(models=[selection(GPT), selection(GPT)]))


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


def test_execution_config_accepts_json_values() -> None:
    config = {"temperature": 0.2, "max_tokens": 512, "stop": ["END"]}

    assert (
        SimulationCreateRequest(**create_body(execution_config=config)).execution_config
        == config
    )


def test_routing_policy_accepts_what_the_database_stores() -> None:
    # simulation_runs.routing_policy 의 실제 저장값(seed). 재실행 초안이 이 값을 그대로 돌려보낸다
    policy = {"allow_fallbacks": False, "require_parameters": True}

    request = SimulationCreateRequest(**create_body(routing_policy=policy))

    assert request.routing_policy.model_dump() == policy


@pytest.mark.parametrize("field", ["allow_fallbacks", "require_parameters"])
def test_each_routing_option_can_be_switched(field: str) -> None:
    for value in (True, False):
        request = SimulationCreateRequest(**create_body(routing_policy={field: value}))
        assert getattr(request.routing_policy, field) is value


def test_routing_policy_rejects_unknown_keys() -> None:
    # order(업체 순서)는 모델 칸마다 execution_provider 로 정해지므로 실행 전체 정책에는 없다
    with pytest.raises(ValidationError):
        SimulationCreateRequest(**create_body(routing_policy={"order": ["DeepInfra"]}))


def test_openapi_lists_test_type_values_and_forbids_extra_fields() -> None:
    # 프론트엔드는 test_type 값을 따로 외우지 않고 OpenAPI 문서에서 받는다
    schema = SimulationCreateRequest.model_json_schema()

    assert schema["properties"]["test_type"]["$ref"].endswith("TestType")
    assert schema["$defs"]["TestType"]["enum"] == ["SCENARIO", "CUSTOM"]
    assert schema["additionalProperties"] is False

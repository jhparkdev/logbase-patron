import pytest

from app.services.simulation_input import (
    DEFAULT_MAX_TOKENS,
    HEARTBEAT_INTERVAL_SECONDS,
    SIMULATION_TIMEOUT_SECONDS,
    InputRequiredError,
    build_messages,
    build_prompt_text,
    build_request_routing_policy,
    build_run_routing_policy,
    compute_input_hash,
    resolve_execution_config,
    resolve_json_schema,
    validate_input_present,
)

TEMPLATE = (
    "다음 상품 정보로 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n{{product_info}}"
)
PRODUCT = (
    "상품명: 린넨 셔츠 원피스 / 가격 59,000원 / 옵션: 베이지, 네이비 / 소재: 린넨 100%"
)


def test_team_decided_numbers() -> None:
    # 팀의 "임시 수치(결정됨)" 표와 하트비트 결정(30초)
    assert SIMULATION_TIMEOUT_SECONDS == 180
    assert HEARTBEAT_INTERVAL_SECONDS == 30
    # 직접 작성 실행처럼 아무도 정하지 않았을 때의 최대 토큰. 사용자 입력 상한과 같다
    assert DEFAULT_MAX_TOKENS == 4096


# --- 프롬프트 합성 ---


def test_placeholder_is_replaced_with_the_input() -> None:
    assert build_prompt_text(TEMPLATE, PRODUCT) == (
        "다음 상품 정보로 상세 설명 3문단과 마케팅 문구 1줄을 작성하세요.\n" + PRODUCT
    )


def test_input_is_appended_when_the_prompt_has_no_placeholder() -> None:
    assert build_prompt_text("강점을 3가지로 정리하세요.", PRODUCT) == (
        "강점을 3가지로 정리하세요.\n\n" + PRODUCT
    )


@pytest.mark.parametrize("input_text", [None, "", "  \n"])
def test_prompt_is_sent_as_is_without_input(input_text: str | None) -> None:
    # 입력 데이터는 선택사항이다. 템플릿 자리가 남아 있어도 사용자가 쓴 글을 바꾸지 않는다
    assert build_prompt_text(TEMPLATE, input_text) == TEMPLATE
    assert build_prompt_text("그냥 질문", input_text) == "그냥 질문"


# --- 입력이 필요한 템플릿 (요청 접수 때 거절) ---


@pytest.mark.parametrize("input_text", [None, "", "   ", "\n\t"])
def test_template_with_a_placeholder_needs_input(input_text: str | None) -> None:
    # 자리를 채우지 못한 채 "{{product_info}}" 라는 글이 모델에 가지 않도록 접수 때 막는다
    with pytest.raises(InputRequiredError):
        validate_input_present(TEMPLATE, input_text)


def test_template_with_input_is_accepted() -> None:
    validate_input_present(TEMPLATE, PRODUCT)


@pytest.mark.parametrize("input_text", [None, "", PRODUCT])
def test_prompt_without_a_placeholder_never_needs_input(
    input_text: str | None,
) -> None:
    validate_input_present("그냥 질문", input_text)


def test_every_placeholder_gets_the_same_input() -> None:
    assert build_prompt_text("{{a}} 와 {{b}}", "X") == "X 와 X"


def test_input_containing_braces_is_not_substituted_again() -> None:
    # 한 번만 치환한다. 입력에 들어 있던 {{...}} 가 다시 바뀌면 사용자가 보낸 글이 달라진다
    assert build_prompt_text("{{a}}", "{{b}} 와 \\1") == "{{b}} 와 \\1"


def test_messages_are_a_single_user_message() -> None:
    # call_model 은 {role, content} 딕셔너리의 목록으로 받는다
    assert build_messages("안녕") == [{"role": "user", "content": "안녕"}]


# --- 입력 해시 (건호님 seed 와 같은 식: sha256(프롬프트 + 입력 텍스트)) ---


def test_input_hash_matches_the_seed_value() -> None:
    seed_hash = "5ded0dc17627410f37955ced6d552d675ca79c4282d38b61e779e58ff198bf23"

    assert compute_input_hash(TEMPLATE, PRODUCT) == seed_hash


def test_input_hash_is_made_from_the_original_pieces_not_the_merged_text() -> None:
    # 합친 글로 계산하면 seed 와 달라진다. 원본 프롬프트와 입력을 쓴다
    assert compute_input_hash(TEMPLATE, PRODUCT) != compute_input_hash(
        build_prompt_text(TEMPLATE, PRODUCT), None
    )


def test_input_hash_treats_missing_input_as_empty() -> None:
    assert compute_input_hash("질문", None) == compute_input_hash("질문", "")


def test_input_hash_changes_when_the_input_changes() -> None:
    assert compute_input_hash("질문", "a") != compute_input_hash("질문", "b")
    assert len(compute_input_hash("질문", "a")) == 64


# --- 시나리오 기본값 ---
# call_model 이 아직 temperature 를 받지 않는다. 보내지 못하는 값을 기록하면 기록과 실제 호출이 달라지므로
# 실제로 보내는 설정(max_tokens)만 남긴다. temperature 인자가 생기면 이 규칙을 되돌린다


def test_scenario_default_fills_in_max_tokens() -> None:
    defaults = {"temperature": 0.7, "max_tokens": 1024}

    assert resolve_execution_config({}, defaults) == {"max_tokens": 1024}


def test_request_value_wins_over_the_scenario_default() -> None:
    defaults = {"temperature": 0.7, "max_tokens": 1024}

    assert resolve_execution_config({"max_tokens": 256}, defaults) == {
        "max_tokens": 256
    }


def test_max_tokens_falls_back_to_the_default_when_nobody_set_it() -> None:
    assert resolve_execution_config({}, None) == {"max_tokens": DEFAULT_MAX_TOKENS}
    assert resolve_execution_config({}, {"temperature": 0}) == {
        "max_tokens": DEFAULT_MAX_TOKENS
    }


def test_settings_that_cannot_be_sent_yet_are_not_recorded() -> None:
    assert resolve_execution_config({"temperature": 0.2}, {"temperature": 0.7}) == {
        "max_tokens": DEFAULT_MAX_TOKENS
    }


def test_json_schema_falls_back_to_the_scenario_default() -> None:
    default = {"type": "object", "required": ["name"]}
    own = {"type": "object", "required": ["title"]}

    assert resolve_json_schema(None, default) == default
    assert resolve_json_schema(own, default) == own
    assert resolve_json_schema(None, None) is None


# --- 라우팅 정책 ---


def test_run_routing_policy_records_require_parameters_only_with_a_schema() -> None:
    # call_model 은 Schema 가 있을 때만 require_parameters 를 켠다. 실제로 보낸 값과 같게 기록한다
    assert build_run_routing_policy(allow_fallbacks=False, has_json_schema=True) == {
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert build_run_routing_policy(allow_fallbacks=False, has_json_schema=False) == {
        "allow_fallbacks": False,
        "require_parameters": False,
    }
    policy = build_run_routing_policy(allow_fallbacks=True, has_json_schema=False)
    assert policy["allow_fallbacks"] is True


def test_request_routing_policy_pins_the_chosen_provider() -> None:
    run_policy = build_run_routing_policy(allow_fallbacks=False, has_json_schema=True)

    assert build_request_routing_policy(run_policy, "DekaLLM") == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "order": ["DekaLLM"],
    }
    # 실행 전체 정책은 바뀌지 않는다
    assert "order" not in run_policy

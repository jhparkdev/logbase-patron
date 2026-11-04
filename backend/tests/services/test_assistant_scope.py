from uuid import UUID

import pytest

from app.schemas.assistant import AssistantChatRequest, AssistantPageContext
from app.services.assistant_scope import request_scope


def request(text: str, page: str | None = None) -> AssistantChatRequest:
    return AssistantChatRequest(
        messages=[{"role": "user", "content": text}],
        page_context=AssistantPageContext(page=page) if page else None,
    )


def test_customer_calls_cannot_be_replaced_by_simulations_even_on_p05() -> None:
    scope = request_scope(
        request("가상고객A의 가장 최근 호출 시각을 알려줘", "simulation_history")
    )
    assert scope.allowed_tools == {"get_customer_usage"}
    assert scope.requires_lookup


def test_named_real_api_calls_on_p05_use_customer_lookup() -> None:
    scope = request_scope(
        request(
            "로웰린 스튜디오의 2026년 10월 가장 최근 실제 API 호출 시각",
            "simulation_history",
        )
    )
    assert scope.allowed_tools == {"get_customer_usage"}
    assert scope.requires_lookup
    assert request_scope(request("내부 프로젝트의 실제 API 호출")).allowed_tools == {
        "get_internal_usage"
    }


def test_settings_and_simulation_results_require_verified_tools() -> None:
    setup = request_scope(request("공통 최대 출력 토큰만 2048로 바꿔줘", "simulator"))
    assert setup.requires_lookup
    assert setup.required_tool == "prepare_simulator_settings"
    detail = request_scope(
        request("이 실행 ID의 결과: 00000000-0000-4000-8000-000000000001")
    )
    assert detail.requires_lookup
    assert detail.required_tool == "get_simulation"


def test_model_queries_and_follow_up_settings_require_their_own_tools() -> None:
    for question in (
        "현재 선택할 수 있는 모델과 서버 업체를 알려줘",
        "등록된 모델 목록을 알려줘",
        "사용 가능한 모델 몇 개야?",
        "등록된 모델 수는?",
    ):
        models = request_scope(request(question, "customer_usage"))
        assert models.requires_lookup
        assert models.required_tool == "find_models"
    follow_up = AssistantChatRequest(
        messages=[{"role": "user", "content": "이번에는 1024로 바꿔줘"}],
        simulator={},
        page_context=AssistantPageContext(page="simulator"),
    )
    assert request_scope(follow_up).required_tool == "prepare_simulator_settings"


def test_current_page_resolves_implicit_customer_and_internal_queries() -> None:
    assert request_scope(
        request("현재 조건의 비용을 정리해줘", "customer_usage")
    ).allowed_tools == {"get_customer_usage"}
    assert request_scope(
        request("선택한 프로젝트 예산을 보여줘", "internal_budget")
    ).allowed_tools == {"get_internal_usage"}


def test_explicit_scope_overrides_current_page_and_setup_is_still_available() -> None:
    assert request_scope(
        request("내부 프로젝트 비용을 알려줘", "customer_usage")
    ).allowed_tools == {"get_internal_usage"}
    assert (
        "prepare_simulator_settings"
        in request_scope(
            request("최대 출력 토큰만 2048로 바꿔줘", "customer_usage")
        ).allowed_tools
    )


@pytest.mark.parametrize(
    "text",
    [
        "이 실행 ID의 결과를 요약해줘: 00000000-0000-4000-8000-000000000001",
        "최근 시뮬레이션 이력을 보여줘",
        "등록된 모델 목록을 알려줘",
        "JSON 스키마를 추천해줘",
        "안녕",
    ],
)
def test_read_only_requests_on_p04_cannot_prepare_settings(text: str) -> None:
    body = AssistantChatRequest(
        messages=[{"role": "user", "content": text}],
        simulator={},
        page_context=AssistantPageContext(page="simulator"),
    )
    assert "prepare_simulator_settings" not in request_scope(body).allowed_tools


def test_ambiguous_calls_and_mixed_domains_require_clarification() -> None:
    assert request_scope(request("최근 API 호출을 알려줘")).clarification
    assert request_scope(
        request("고객 호출과 시뮬레이션 비용을 섞어 집계해줘")
    ).clarification
    assert request_scope(
        request("선택한 고객 예산을 100달러로 바꿔줘", "customer_usage")
    ).clarification


def test_follow_up_can_reuse_the_previous_explicit_domain_off_dashboard() -> None:
    body = AssistantChatRequest(
        messages=[
            {"role": "user", "content": "가상고객A 비용을 알려줘"},
            {"role": "assistant", "content": "조회 결과예요."},
            {"role": "user", "content": "이번 달은?"},
        ],
        page_context=AssistantPageContext(page="models"),
    )
    assert request_scope(body).allowed_tools == {"get_customer_usage"}


@pytest.mark.parametrize(
    "text",
    [
        "선택한 실행의 결과를 비교해줘",
        "어떤 모델이 더 빠르고 저렴했어?",
        "모델별 입력 출력 토큰 차이를 알려줘",
        "JSON 검증 결과를 비교해줘",
        "비교해줘",
        "어느 모델이 더 빨랐어?",
        "최저 비용 모델을 알려줘",
        "가장 응답시간이 짧은 모델은?",
        "모델별 비용과 응답시간을 알려줘",
    ],
)
def test_selected_run_comparisons_use_the_server_selected_id(text: str) -> None:
    run_id = UUID("00000000-0000-4000-8000-000000000001")
    body = request(text, "simulation_history")
    body.page_context.simulation_id = run_id
    scope = request_scope(body)
    assert scope.comparison_id == run_id
    assert scope.allowed_tools == {"get_simulation"}


def test_comparison_requires_one_explicit_or_selected_run() -> None:
    assert request_scope(request("시뮬레이션 결과를 정량 비교해줘")).clarification
    ids = "00000000-0000-4000-8000-000000000001 00000000-0000-4000-8000-000000000002"
    assert request_scope(request(f"두 실행의 결과 비교: {ids}")).clarification
    explicit = request_scope(
        request(f"실행 결과 비교: {ids.split()[0]}", "customer_usage")
    )
    assert str(explicit.comparison_id) == ids.split()[0]


def test_catalog_recommendations_are_not_reinterpreted_as_past_run_rankings() -> None:
    body = request("가장 저렴한 모델을 추천해줘", "simulator")
    body.page_context.simulation_id = UUID("00000000-0000-4000-8000-000000000001")
    assert request_scope(body).comparison_id is None


@pytest.mark.parametrize(
    "text",
    [
        (
            "시뮬레이터를 세팅해줘. 모델은 가장 많이 사용 된 3개, provider가 여럿이라면 "
            "가장 저렴한 것으로 선택해줘. 이미지는 없고, 'LOGBASE Patron 서비스를 "
            "간단하게 소개해줘' 라는 프롬프트를 입력할거야"
        ),
        "가장 저렴한 업체로 선택해줘",
        "가장 빠른 모델 두 개를 지정해줘",
        "시뮬레이터 세팅해줘. Prompt는 '소개해줘'로 입력해줘",
    ],
)
def test_settings_requests_with_ranking_words_are_not_run_comparisons(
    text: str,
) -> None:
    body = AssistantChatRequest(
        messages=[{"role": "user", "content": text}],
        simulator={},
        page_context=AssistantPageContext(
            page="simulator", simulation_id="00000000-0000-4000-8000-000000000001"
        ),
    )
    scope = request_scope(body)
    assert scope.comparison_id is None
    assert scope.clarification is None
    assert scope.required_tool == "prepare_simulator_settings"


def test_comparison_does_not_override_customer_scope_or_settings() -> None:
    assert request_scope(
        request("고객 모델별 비용을 비교해줘", "simulation_history")
    ).allowed_tools == {"get_customer_usage"}
    assert (
        request_scope(request("토큰을 2048로 바꿔줘", "simulator")).required_tool
        == "prepare_simulator_settings"
    )


SETUP_WITH_QUOTED_USAGE_WORDS = (
    "최근 등록된 모델 2개로 비교 모델을 설정하고 각각 실행 업체도 지정해줘. "
    '공통 최대 출력 토큰은 1024로 설정하고, Prompt는 "LOGBASE Patron 서비스를 세 줄로 '
    '소개해줘"로, 입력 텍스트는 "Patron은 AI 사용량과 비용을 관리하는 관리자 콘솔이다"로 '
    "바꿔줘."
)


@pytest.mark.parametrize("page", ["customer_usage", "simulator"])
def test_quoted_prompt_or_input_text_is_content_not_the_request_intent(
    page: str,
) -> None:
    body = AssistantChatRequest(
        messages=[{"role": "user", "content": SETUP_WITH_QUOTED_USAGE_WORDS}],
        simulator={} if page == "simulator" else None,
        page_context=AssistantPageContext(page=page),
    )

    scope = request_scope(body)

    assert scope.clarification is None
    assert scope.required_tool == "prepare_simulator_settings"
    assert "get_customer_usage" not in scope.allowed_tools


@pytest.mark.parametrize("quote", ['"{}"', "'{}'", "“{}”", "‘{}’", "「{}」"])
def test_each_quote_style_is_treated_as_content(quote: str) -> None:
    text = f"Prompt를 {quote.format('고객 사용량을 요약해줘')}로 바꿔줘"

    scope = request_scope(request(text, "customer_usage"))

    assert scope.required_tool == "prepare_simulator_settings"


def test_a_quoted_run_id_is_still_read_for_comparison() -> None:
    run_id = "00000000-0000-4000-8000-000000000001"

    scope = request_scope(request(f"실행 결과 비교: '{run_id}'", "customer_usage"))

    assert str(scope.comparison_id) == run_id

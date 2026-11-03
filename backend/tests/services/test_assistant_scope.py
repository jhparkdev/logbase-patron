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

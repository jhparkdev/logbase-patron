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

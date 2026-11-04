import pytest

from app.services.assistant_models import model_answer, model_lookup_kind


@pytest.mark.parametrize(
    "text",
    [
        "지금 사용 가능한 모델의 개수를 알려주세요",
        "사용 중인 모델은 몇 개야?",
        "등록된 활성 모델 수가 궁금해",
    ],
)
def test_model_count_questions_are_recognized_without_requiring_a_list(
    text: str,
) -> None:
    assert model_lookup_kind(text) == "count"


@pytest.mark.parametrize(
    "text",
    ["모델 목록을 보여줘", "모델 개수와 이름도 알려줘", "모델의 제공사를 알려줘"],
)
def test_model_names_and_creators_do_not_request_execution_providers(text: str) -> None:
    assert model_lookup_kind(text) == "list"


@pytest.mark.parametrize(
    "text",
    [
        "Haiku의 실행 업체는?",
        "어느 서버 업체로 실행할 수 있어?",
        "모델의 Provider가 몇 개야?",
        "모델 A와 B를 선택해줘",
    ],
)
def test_execution_provider_queries_and_model_selection_request_endpoints(
    text: str,
) -> None:
    assert model_lookup_kind(text) == "providers"


def test_count_answer_uses_total_without_listing_names_or_endpoints() -> None:
    answer = model_answer({"view": "count", "total": 10, "items": []})
    assert answer == "전체 등록 모델 기준, 사용 중 상태는 10개예요."


def test_list_shows_creator_and_explicit_page_range_without_endpoint_names() -> None:
    answer = model_answer(
        {
            "total": 12,
            "page": 2,
            "page_size": 5,
            "items": [
                {
                    "name": "모델 A",
                    "creator": "Anthropic",
                    "providers": [{"execution_provider": "Google"}],
                },
                {"name": "모델 B", "creator": "OpenAI", "providers": []},
            ],
        }
    )
    assert answer.startswith("지금 사용 가능한 모델은 12개입니다.\n\n- 모델 A")
    assert "6~7번째 모델을 표시했어요." in answer
    assert "다음 페이지 보여줘" in answer
    assert "모델 A — 모델 제공사: Anthropic" in answer
    assert "Google" not in answer
    assert "서버 업체 정보 확인 불가" not in answer


def test_provider_answer_labels_available_routes_and_does_not_claim_actual_execution() -> (
    None
):
    answer = model_answer(
        {
            "view": "providers",
            "total": 1,
            "page": 1,
            "page_size": 5,
            "items": [
                {
                    "name": "Haiku",
                    "creator": "Anthropic",
                    "providers": [
                        {"execution_provider": "Google"},
                        {"execution_provider": "AWS"},
                    ],
                }
            ],
        }
    )
    assert "모델 제공사: Anthropic" in answer
    assert "실행 업체: Google, AWS" in answer
    assert "실제 호출 성공을 검증한 결과는 아니에요" in answer
    assert "번째 모델을 표시했어요" not in answer
    assert "다음 페이지 보여줘" not in answer


@pytest.mark.parametrize("total,page", [(0, 1), (10, 3)])
def test_empty_pages_never_print_an_impossible_range(total: int, page: int) -> None:
    answer = model_answer({"total": total, "page": page, "page_size": 5, "items": []})
    assert "번째" not in answer
    assert ("없어요" if total == 0 else "이 페이지") in answer


def test_search_scope_and_empty_provider_results_are_explicit() -> None:
    answer = model_answer(
        {
            "view": "providers",
            "q": "Haiku",
            "total": 1,
            "items": [{"name": "Haiku", "creator": "Anthropic", "providers": []}],
        }
    )
    assert answer.startswith("‘Haiku’ 검색 결과에서 사용 가능한 모델은 1개입니다.")
    assert "실행 업체: 확인하지 못했어요" in answer


def test_pagination_followup_keeps_the_previous_provider_request() -> None:
    assert (
        model_lookup_kind("다음 페이지", ("모델의 서버 업체 목록을 알려줘",))
        == "providers"
    )
    assert model_lookup_kind("다음 페이지", ("모델 개수", "모델 목록")) == "list"


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("업체 정보 없이 모델 개수만 알려줘", "count"),
        ("실행 업체는 빼고 모델 목록만 보여줘", "list"),
    ],
)
def test_explicit_omission_of_providers_does_not_trigger_endpoint_fetches(
    text: str, kind: str
) -> None:
    assert model_lookup_kind(text) == kind


def model_row(name: str, price: str | None = None) -> dict:
    return {
        "name": name,
        "creator": "vendor",
        "providers": [],
        "price": {"input_usd_per_token": price, "output_usd_per_token": price}
        if price is not None
        else None,
    }


def test_recent_sort_states_the_registration_order_basis() -> None:
    answer = model_answer(
        {"sort": "recent", "total": 1, "items": [model_row("새 모델")]}
    )

    assert "최근 등록순" in answer


def test_price_sort_shows_input_price_per_million_tokens_and_unknown_prices() -> None:
    answer = model_answer(
        {
            "sort": "price",
            "total": 2,
            "items": [model_row("싼 모델", "0.0000001"), model_row("미확인 모델")],
        }
    )

    assert "입력 단가 낮은순" in answer
    assert "싼 모델 — 모델 제공사: vendor · 입력 0.1 USD / 100만 토큰" in answer
    # 가격을 모르는 모델을 0으로 보이지 않는다.
    assert "미확인 모델 — 모델 제공사: vendor · 입력 단가 미확인" in answer


def test_name_sort_does_not_add_a_basis_line() -> None:
    answer = model_answer({"sort": "name", "total": 1, "items": [model_row("모델")]})

    assert "등록순" not in answer
    assert "단가" not in answer

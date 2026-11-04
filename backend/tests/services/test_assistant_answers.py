from app.services.assistant_answers import verified_answer


def usage(data: dict, *, internal: bool = False, section: str = "summary") -> dict:
    return {
        "section": section,
        "conditions": {"start_date": "2026-10-01", "end_date": "2026-10-31"},
        "matched_entities": {"project" if internal else "customer": "선택 대상"},
        "data": data,
    }


def test_internal_summary_uses_the_service_total_without_inventing_an_extra_fee() -> (
    None
):
    answer = verified_answer(
        "get_internal_usage",
        usage(
            {
                "api_confirmed_usd": "1.8905200425",
                "api_estimated_usd": "0.00078126",
                "subscription_usd": "30.0000",
                "total_managed_usd": "31.8913013025",
                "unknown_cost_count": 8,
                "subscription_excluded": False,
            },
            internal=True,
        ),
    )
    assert "관리 비용(추정 포함): 31.8913013025 USD" in answer
    assert "확정 API 비용: 1.8905200425 USD" in answer
    assert "추정 API 비용: 0.00078126 USD" in answer
    assert "구독료: 30 USD" in answer
    assert "금액 미확인 8건은 합계에서 제외" in answer


def test_model_filter_excludes_subscriptions_instead_of_calling_them_unset() -> None:
    answer = verified_answer(
        "get_internal_usage",
        usage(
            {
                "api_confirmed_usd": "0.06",
                "api_estimated_usd": "0",
                "subscription_usd": None,
                "total_managed_usd": "0.06",
                "unknown_cost_count": 1,
                "subscription_excluded": True,
            },
            internal=True,
        ),
    )
    assert "모델 필터로 구독료는 제외" in answer
    assert "미설정" not in answer


def test_customer_summary_keeps_estimated_cost_separate_from_confirmed() -> None:
    answer = verified_answer(
        "get_customer_usage",
        usage(
            {
                "confirmed_cost_usd": "4.1360762325",
                "estimated_cost_usd": "0.057354285",
                "unknown_cost_count": 20,
            }
        ),
    )
    assert "확정 API 비용: 4.1360762325 USD" in answer
    assert "추정 API 비용: 0.057354285 USD" in answer
    assert "미확인 20건" in answer


def test_latest_call_uses_the_returned_timestamp_and_keeps_unknown_cost_unknown() -> (
    None
):
    answer = verified_answer(
        "get_customer_usage",
        usage(
            {
                "items": [
                    {
                        "requested_at": "2026-10-31T11:03:00Z",
                        "cost_usd": None,
                        "cost_status": "UNKNOWN",
                    }
                ],
                "total": 623,
                "page": 1,
            },
            section="requests",
        ),
    )
    assert "2026-10-31T11:03:00Z" in answer
    assert "비용 미확인" in answer
    assert "0 USD" not in answer


def test_simulation_detail_uses_stored_cost_and_time_instead_of_model_claims() -> None:
    answer = verified_answer(
        "get_simulation",
        {
            "summary": {
                "status": "SUCCESS",
                "requested_at": "2026-10-29T04:35:00Z",
                "total_cost_usd": "0.0017718134",
                "cost_check_status": "확정",
                "unknown_cost_count": 0,
            },
            "results": [],
        },
    )
    assert "0.0017718134 USD" in answer
    assert "2026-10-29T04:35:00Z" in answer
    assert "성공" in answer
    assert "원" not in answer


def test_history_does_not_sum_the_current_page_or_turn_unknown_cost_into_zero() -> None:
    answer = verified_answer(
        "list_simulations",
        {
            "total": 19,
            "items": [
                {
                    "status": "CANCELLED",
                    "requested_at": "2026-10-28T07:05:00Z",
                    "total_cost_usd": None,
                    "cost_check_status": "미확인 포함",
                    "unknown_cost_count": 2,
                }
            ],
        },
    )
    assert "전체 19건 중 1건" in answer
    assert "비용 미확인" in answer
    assert "총합" not in answer
    assert "0 USD" not in answer


def test_models_only_show_providers_that_the_catalog_actually_returned() -> None:
    answer = verified_answer(
        "find_models",
        {
            "view": "providers",
            "total": 12,
            "items": [
                {"name": "모델 A", "providers": []},
                {"name": "모델 B", "providers": [{"execution_provider": "실제 업체"}]},
            ],
        },
    )
    assert "지금 사용 가능한 모델은 12개입니다." in answer
    assert "1~2번째 모델을 표시했어요." in answer
    assert "실행 업체: 확인하지 못했어요" in answer
    assert "실행 업체: 실제 업체" in answer

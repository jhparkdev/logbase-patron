from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.simulation import SimulationCreateRequest
from app.schemas.simulation_history import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    SimulationHistoryPage,
    SimulationHistoryQuery,
    SimulationRerunDraft,
)
from app.services.simulation_sort import SortColumn, SortDirection

PAST_ID = "0192a3c4-0000-7000-8000-000000000001"


def test_query_defaults_to_latest_first_first_page() -> None:
    query = SimulationHistoryQuery()

    assert query.start_date is None
    assert query.end_date is None
    assert query.sort == SortColumn.REQUESTED_AT
    assert query.direction == SortDirection.DESC
    assert (query.page, query.page_size) == (1, DEFAULT_PAGE_SIZE)


def test_query_reads_dates_as_calendar_days() -> None:
    query = SimulationHistoryQuery(start_date="2026-10-01", end_date="2026-10-28")

    assert (query.start_date, query.end_date) == (date(2026, 10, 1), date(2026, 10, 28))


# 페이지 경계는 바로 전, 정확히 그 값, 바로 후를 모두 검사한다
@pytest.mark.parametrize("page", [1, 2])
def test_page_from_one_is_accepted(page: int) -> None:
    assert SimulationHistoryQuery(page=page).page == page


def test_page_below_one_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(page=0)


@pytest.mark.parametrize("size", [1, MAX_PAGE_SIZE - 1, MAX_PAGE_SIZE])
def test_page_size_within_limit_is_accepted(size: int) -> None:
    assert SimulationHistoryQuery(page_size=size).page_size == size


@pytest.mark.parametrize("size", [0, MAX_PAGE_SIZE + 1])
def test_page_size_outside_limit_is_rejected(size: int) -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(page_size=size)


@pytest.mark.parametrize("column", [column.value for column in SortColumn])
def test_every_allowed_sort_column_is_accepted(column: str) -> None:
    assert SimulationHistoryQuery(sort=column).sort == column


@pytest.mark.parametrize("column", ["prompt_text", "executed_by; DROP TABLE", ""])
def test_sort_column_outside_the_allow_list_is_rejected(column: str) -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(sort=column)


def test_sort_direction_outside_asc_desc_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(direction="up")


def test_query_rejects_unknown_parameters() -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(project_id=1)


def test_openapi_carries_sort_allow_list_and_page_limits() -> None:
    # 프론트엔드는 정렬 열과 한도를 따로 외우지 않고 OpenAPI 문서에서 받는다
    schema = SimulationHistoryQuery.model_json_schema()

    assert schema["$defs"]["SortColumn"]["enum"] == [c.value for c in SortColumn]
    assert schema["properties"]["page_size"]["maximum"] == MAX_PAGE_SIZE


def summary_body() -> dict[str, object]:
    return {
        "simulation_id": PAST_ID,
        "rerun_of_simulation_id": None,
        "test_type": "CUSTOM",
        "scenario_code": None,
        "status": "SUCCESS",
        "model_count": 2,
        "requested_at": "2026-10-28T01:00:00Z",
        "completed_at": "2026-10-28T01:00:09Z",
        "executed_by": 1,
        "final_result_count": 2,
        "success_count": 2,
        "failure_count": 0,
        "confirmed_cost_usd": "0.000123",
        "estimated_cost_usd": None,
        "unknown_cost_count": 0,
        "cost_check_status": "확정",
    }


def test_history_page_holds_summaries_and_total() -> None:
    page = SimulationHistoryPage(items=[summary_body()], total=120)

    dumped = page.model_dump(mode="json")
    assert dumped["total"] == 120
    assert dumped["items"][0]["confirmed_cost_usd"] == "0.000123"
    assert dumped["items"][0]["estimated_cost_usd"] is None


def test_empty_history_is_a_valid_page() -> None:
    assert SimulationHistoryPage(items=[], total=0).items == []


def draft_body(**overrides: object) -> dict[str, object]:
    """과거 직접 작성(CUSTOM) 실행의 입력값. 필요한 값만 덮어써서 쓴다."""
    body: dict[str, object] = {
        "rerun_of_simulation_id": PAST_ID,
        "test_type": "CUSTOM",
        "scenario_id": None,
        "prompt_text": "  상품 설명을 써 주세요\n",
        "input_text": None,
        "json_schema": {"type": "object", "required": ["title"]},
        "execution_config": {"temperature": 0.2},
        "routing_policy": {"allow_fallbacks": False, "require_parameters": True},
        "models": [
            {"model_id": 1, "execution_provider": "DeepInfra"},
            {"model_id": 2, "execution_provider": "DekaLLM"},
        ],
    }
    body.update(overrides)
    return body


def test_draft_returns_the_past_inputs_unchanged() -> None:
    dumped = SimulationRerunDraft(**draft_body()).model_dump(mode="json")

    assert dumped == draft_body()


def test_draft_points_back_to_the_original_run() -> None:
    body = draft_body()
    del body["rerun_of_simulation_id"]

    with pytest.raises(ValidationError):
        SimulationRerunDraft(**body)


def test_draft_inputs_can_be_sent_back_as_a_new_run_request() -> None:
    # 화면은 초안을 채워 놓고 사용자가 고친 값을 비교 실행 요청으로 보낸다. 두 모양이 어긋나면 안 된다
    # 원본 실행 ID 도 함께 넘어가므로 새 실행이 어느 실행의 재실행인지 남는다
    sent = SimulationRerunDraft(**draft_body()).model_dump(mode="json")

    request = SimulationCreateRequest(**sent)

    assert request.models[0].model_id == 1
    assert str(request.rerun_of_simulation_id) == PAST_ID


def test_draft_has_no_server_owned_values() -> None:
    # 비용 귀속(project_id·key_id)과 실행자는 새 실행 때 서버가 다시 정한다
    fields = set(SimulationRerunDraft.model_fields)

    assert fields.isdisjoint(
        {"project_id", "key_id", "executed_by", "status", "input_hash", "data_source"}
    )


def test_draft_keeps_past_selection_even_if_todays_duplicate_rule_would_reject_it() -> (
    None
):
    # 과거 이력은 지금 규칙으로 다시 거절하지 않는다. 새 실행 요청에서 다시 검증한다
    same_twice = [{"model_id": 1, "execution_provider": "DeepInfra"}] * 2

    assert len(SimulationRerunDraft(**draft_body(models=same_twice)).models) == 2


@pytest.mark.parametrize("count", [1, 5])
def test_draft_model_count_is_limited_like_the_database(count: int) -> None:
    models = [{"model_id": n, "execution_provider": "P"} for n in range(count)]

    with pytest.raises(ValidationError):
        SimulationRerunDraft(**draft_body(models=models))

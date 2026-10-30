from datetime import date

import pytest
from pydantic import ValidationError

from app.models import SimulationStatus
from app.schemas.simulation import SimulationCreateRequest
from app.schemas.simulation_history import (
    MAX_HISTORY_ITEMS,
    RerunBlockReason,
    SimulationHistoryList,
    SimulationHistoryQuery,
    SimulationRerunDraft,
)

PAST_ID = "0192a3c4-0000-7000-8000-000000000001"


def test_query_has_no_period_by_default() -> None:
    query = SimulationHistoryQuery()

    assert query.start_date is None
    assert query.end_date is None


def test_query_reads_dates_as_calendar_days() -> None:
    query = SimulationHistoryQuery(start_date="2026-10-01", end_date="2026-10-28")

    assert (query.start_date, query.end_date) == (date(2026, 10, 1), date(2026, 10, 28))


@pytest.mark.parametrize(
    "parameter",
    [{"sort": "requested_at"}, {"direction": "asc"}, {"page": 1}, {"page_size": 10}],
)
def test_sorting_and_paging_are_not_server_parameters(
    parameter: dict[str, object],
) -> None:
    # 정렬과 페이지는 화면이 한다(팀 결정). 받는 척하고 무시하면 화면이 서버 정렬을 믿게 되므로 거절한다
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(**parameter)


def test_query_rejects_unknown_parameters() -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(project_id=1)


def test_filters_are_off_by_default() -> None:
    query = SimulationHistoryQuery()

    assert (query.scenario_id, query.model_id, query.status) == (None, None, None)
    assert query.simulation_id is None


def test_filters_accept_the_values_the_history_screen_sends() -> None:
    query = SimulationHistoryQuery(
        scenario_id=7, model_id=3, status="PARTIAL_SUCCESS", simulation_id=PAST_ID
    )

    assert (query.scenario_id, query.model_id) == (7, 3)
    assert query.status == SimulationStatus.PARTIAL_SUCCESS
    assert str(query.simulation_id) == PAST_ID


@pytest.mark.parametrize("status", [status.value for status in SimulationStatus])
def test_every_simulation_status_is_a_valid_filter(status: str) -> None:
    assert SimulationHistoryQuery(status=status).status == status


@pytest.mark.parametrize(
    "field, value",
    [
        ("status", "DONE"),
        ("scenario_id", "scenario"),
        ("model_id", "gpt"),
        ("simulation_id", "not-a-uuid"),
    ],
)
def test_filter_values_outside_the_contract_are_rejected(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        SimulationHistoryQuery(**{field: value})


def test_openapi_lists_the_status_filter_values() -> None:
    schema = SimulationHistoryQuery.model_json_schema()

    assert schema["$defs"]["SimulationStatus"]["enum"] == [
        status.value for status in SimulationStatus
    ]


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


def test_history_list_holds_summaries_and_the_full_count() -> None:
    history = SimulationHistoryList(items=[summary_body()], total=1, truncated=False)

    dumped = history.model_dump(mode="json")
    assert (dumped["total"], dumped["truncated"]) == (1, False)
    assert dumped["items"][0]["confirmed_cost_usd"] == "0.000123"
    assert dumped["items"][0]["estimated_cost_usd"] is None


def test_empty_history_is_a_valid_list() -> None:
    history = SimulationHistoryList(items=[], total=0, truncated=False)

    assert history.items == []


def test_a_cut_list_says_so() -> None:
    # 상한에 걸려 일부만 준 목록이다. 화면은 "일부만 표시" 를 알리고, 잘린 목록을 전체처럼 정렬해 보이지 않는다
    history = SimulationHistoryList(items=[summary_body()], total=1500, truncated=True)

    assert history.truncated is True


@pytest.mark.parametrize(
    ("total", "truncated"), [(1, True), (2, False)], ids=["claims-cut", "hides-cut"]
)
def test_truncated_must_agree_with_the_count(total: int, truncated: bool) -> None:
    with pytest.raises(ValidationError, match="truncated"):
        SimulationHistoryList(items=[summary_body()], total=total, truncated=truncated)


def test_the_item_limit_is_a_thousand() -> None:
    assert MAX_HISTORY_ITEMS == 1000


def rerun_model(**overrides: object) -> dict[str, object]:
    """재실행 초안의 모델 한 칸. 과거 선택에 현재 이름·상태·선택 가능 여부가 붙는다."""
    body: dict[str, object] = {
        "model_id": 1,
        "execution_provider": "DeepInfra",
        "current_display_name": "Mistral Nemo",
        "current_status": "ACTIVE",
        "selectable": True,
    }
    body.update(overrides)
    return body


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
        "routing_policy": {"allow_fallbacks": False},
        "models": [
            rerun_model(model_id=1, execution_provider="DeepInfra"),
            rerun_model(model_id=2, execution_provider="DekaLLM"),
        ],
        "rerunnable": True,
        "blocked_reason": None,
    }
    body.update(overrides)
    return body


def test_draft_reads_the_routing_policy_the_database_stored() -> None:
    # 과거 기록(seed)에는 서버가 적어 둔 require_parameters 가 들어 있다. 거절하지 않고, 사용자가 고칠 값만 돌려준다
    stored = {"allow_fallbacks": False, "require_parameters": True}

    draft = SimulationRerunDraft(**draft_body(routing_policy=stored))

    assert draft.model_dump(mode="json")["routing_policy"] == {"allow_fallbacks": False}


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
    # 원본 실행 ID 도 함께 넘어가므로 새 실행이 어느 실행의 재실행인지 남는다.
    # rerunnable·blocked_reason 은 화면 안내용이라 새 실행 요청에는 싣지 않는다
    sent = SimulationRerunDraft(**draft_body()).model_dump(
        mode="json", exclude={"rerunnable", "blocked_reason"}
    )

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
    same_twice = [rerun_model(), rerun_model()]

    assert len(SimulationRerunDraft(**draft_body(models=same_twice)).models) == 2


@pytest.mark.parametrize("count", [1, 5])
def test_draft_model_count_is_limited_like_the_database(count: int) -> None:
    models = [rerun_model(model_id=n) for n in range(count)]

    with pytest.raises(ValidationError):
        SimulationRerunDraft(**draft_body(models=models))


def test_draft_shows_which_past_models_can_no_longer_be_chosen() -> None:
    # 비활성 모델은 막지 않고 교체·제외하도록 안내한다 (기준서 8.4). 과거 이름은 그대로 두고 현재 상태를 보여 준다
    inactive = rerun_model(model_id=2, current_status="INACTIVE", selectable=False)

    draft = SimulationRerunDraft(**draft_body(models=[rerun_model(), inactive]))

    assert [m.selectable for m in draft.models] == [True, False]
    assert draft.models[1].current_status == "INACTIVE"
    assert draft.rerunnable is True


@pytest.mark.parametrize(
    "field", ["current_display_name", "current_status", "selectable"]
)
def test_rerun_model_requires_its_current_state(field: str) -> None:
    model = rerun_model()
    del model[field]

    with pytest.raises(ValidationError):
        SimulationRerunDraft(**draft_body(models=[model, rerun_model(model_id=2)]))


def test_rerun_model_current_status_must_be_a_model_status() -> None:
    with pytest.raises(ValidationError):
        SimulationRerunDraft(
            **draft_body(
                models=[rerun_model(current_status="DELETED"), rerun_model(model_id=2)]
            )
        )


def test_blocked_draft_carries_the_reason() -> None:
    # 저장된 입력을 복원할 수 없으면 재실행을 제한하고 사유를 보여 준다 (기준서 8.6)
    draft = SimulationRerunDraft(
        **draft_body(rerunnable=False, blocked_reason="INPUT_MISSING")
    )

    assert draft.blocked_reason == RerunBlockReason.INPUT_MISSING


@pytest.mark.parametrize(
    "rerunnable, reason",
    [(True, "INPUT_MISSING"), (False, None)],
)
def test_rerunnable_and_blocked_reason_must_agree(
    rerunnable: bool, reason: str | None
) -> None:
    with pytest.raises(ValidationError, match="blocked_reason"):
        SimulationRerunDraft(**draft_body(rerunnable=rerunnable, blocked_reason=reason))


def test_openapi_lists_the_block_reasons() -> None:
    schema = SimulationRerunDraft.model_json_schema()

    assert schema["$defs"]["RerunBlockReason"]["enum"] == ["INPUT_MISSING"]

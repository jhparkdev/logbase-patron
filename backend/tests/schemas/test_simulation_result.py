from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.simulation_result import (
    CostCheckStatus,
    SimulationDetailResponse,
    SimulationModelResult,
    SimulationSummary,
)

RUN_ID = "0192a3c4-0000-7000-8000-000000000001"
REQUEST_ID = "0192a3c4-0000-7000-8000-000000000002"


def summary_body(**overrides: object) -> dict[str, object]:
    """v_simulation_summary 한 행과 같은 모양의 요약. 필요한 값만 덮어써서 쓴다."""
    body: dict[str, object] = {
        "simulation_id": RUN_ID,
        "rerun_of_simulation_id": None,
        "test_type": "SCENARIO",
        "scenario_code": "PRODUCT_COPY",
        "status": "PARTIAL_SUCCESS",
        "model_count": 3,
        "requested_at": "2026-10-28T01:00:00Z",
        "completed_at": "2026-10-28T01:00:09Z",
        "executed_by": 1,
        "final_result_count": 3,
        "success_count": 2,
        "failure_count": 1,
        "confirmed_cost_usd": "0.000123",
        "estimated_cost_usd": None,
        "unknown_cost_count": 1,
        "cost_check_status": "미확인 포함",
    }
    body.update(overrides)
    return body


def result_body(**overrides: object) -> dict[str, object]:
    """성공한 모델 한 칸의 결과. 필요한 값만 덮어써서 쓴다."""
    body: dict[str, object] = {
        "slot_no": 1,
        "request_id": REQUEST_ID,
        "model_id": 1,
        "model_display_name_at_run": "Mistral Nemo",
        "model_status_at_run": "ACTIVE",
        "execution_provider": "DeepInfra",
        "execution_config": {"max_tokens": 4096},
        "actual_provider": "DeepInfra",
        "actual_model": "mistralai/mistral-nemo",
        "status": "SUCCESS",
        "error_type": None,
        "latency_ms": 1830,
        "input_tokens": 16,
        "output_tokens": 2,
        "cost_usd": "0.000000348",
        "cost_status": "CONFIRMED",
        "json_parse_status": "PASSED",
        "schema_validation_status": "PASSED",
        "missing_required_fields": [],
        "comparability_note": None,
        "response_text": None,
        "error_message": None,
    }
    body.update(overrides)
    return body


def test_summary_accepts_a_view_row_and_writes_money_as_strings() -> None:
    dumped = SimulationSummary(**summary_body()).model_dump(mode="json")

    assert dumped["confirmed_cost_usd"] == "0.000123"
    assert dumped["success_count"] == 2
    assert dumped["cost_check_status"] == "미확인 포함"


def test_summary_total_with_no_matching_calls_stays_null_never_zero() -> None:
    # SUM 은 대상이 없으면 NULL 이다. "해당 건 없음"을 0 으로 바꾸면 지출이 왜곡된다
    dumped = SimulationSummary(**summary_body(estimated_cost_usd=None)).model_dump(
        mode="json"
    )

    assert dumped["estimated_cost_usd"] is None


def test_cost_check_status_values_come_from_the_view() -> None:
    schema = SimulationSummary.model_json_schema()

    assert schema["$defs"]["CostCheckStatus"]["enum"] == [
        "확인 중",
        "미확인 포함",
        "추정 포함",
        "확정",
    ]
    assert {status.value for status in CostCheckStatus} == {
        "확인 중",
        "미확인 포함",
        "추정 포함",
        "확정",
    }


def test_summary_rejects_a_status_the_view_never_returns() -> None:
    with pytest.raises(ValidationError):
        SimulationSummary(**summary_body(cost_check_status="모름"))


@pytest.mark.parametrize(
    "field", ["success_count", "failure_count", "unknown_cost_count"]
)
def test_counts_reject_negative_and_accept_zero(field: str) -> None:
    assert getattr(SimulationSummary(**summary_body(**{field: 0})), field) == 0
    with pytest.raises(ValidationError):
        SimulationSummary(**summary_body(**{field: -1}))


# model_count 는 DB 제약(2~4)과 같다. 바로 전, 정확히 그 값, 바로 후를 검사한다
@pytest.mark.parametrize("count", [2, 3, 4])
def test_model_count_within_range_is_accepted(count: int) -> None:
    assert SimulationSummary(**summary_body(model_count=count)).model_count == count


@pytest.mark.parametrize("count", [1, 5])
def test_model_count_outside_range_is_rejected(count: int) -> None:
    with pytest.raises(ValidationError):
        SimulationSummary(**summary_body(model_count=count))


def test_summary_times_are_utc_with_timezone() -> None:
    dumped = SimulationSummary(**summary_body()).model_dump(mode="json")

    assert dumped["requested_at"] == "2026-10-28T01:00:00Z"


def test_summary_rejects_a_time_without_timezone() -> None:
    # 시간대가 빠진 시각이 나가면 화면의 KST 변환이 9시간 틀어진다
    with pytest.raises(ValidationError):
        SimulationSummary(**summary_body(requested_at=datetime(2026, 10, 28, 1, 0)))


def test_running_summary_has_no_completed_time() -> None:
    summary = SimulationSummary(**summary_body(status="RUNNING", completed_at=None))

    assert summary.completed_at is None


def test_model_result_accepts_a_successful_row() -> None:
    dumped = SimulationModelResult(**result_body()).model_dump(mode="json")

    assert dumped["cost_usd"] == "0.000000348"
    assert dumped["json_parse_status"] == "PASSED"


def test_unknown_cost_must_be_null() -> None:
    # cost_status=UNKNOWN <=> cost_usd IS NULL (DB CHECK 와 같은 규칙)
    result = SimulationModelResult(
        **result_body(cost_status="UNKNOWN", cost_usd=None, status="TIMEOUT")
    )

    assert result.cost_usd is None


def test_unknown_cost_written_as_zero_is_rejected() -> None:
    with pytest.raises(ValidationError, match="UNKNOWN"):
        SimulationModelResult(**result_body(cost_status="UNKNOWN", cost_usd="0"))


@pytest.mark.parametrize("cost_status", ["CONFIRMED", "ESTIMATED"])
def test_known_cost_status_requires_an_amount(cost_status: str) -> None:
    with pytest.raises(ValidationError, match="cost_usd"):
        SimulationModelResult(**result_body(cost_status=cost_status, cost_usd=None))


def test_estimated_cost_with_an_amount_is_accepted() -> None:
    result = SimulationModelResult(**result_body(cost_status="ESTIMATED"))

    assert result.cost_status == "ESTIMATED"


def test_tokens_and_latency_can_be_unknown_but_not_negative() -> None:
    result = SimulationModelResult(
        **result_body(latency_ms=None, input_tokens=None, output_tokens=None)
    )
    assert (result.latency_ms, result.input_tokens, result.output_tokens) == (
        None,
        None,
        None,
    )

    for field in ("latency_ms", "input_tokens", "output_tokens"):
        assert getattr(SimulationModelResult(**result_body(**{field: 0})), field) == 0
        with pytest.raises(ValidationError):
            SimulationModelResult(**result_body(**{field: -1}))


# slot_no 는 DB 제약(1~4)과 같다
@pytest.mark.parametrize("slot_no", [1, 2, 3, 4])
def test_slot_number_within_range_is_accepted(slot_no: int) -> None:
    assert SimulationModelResult(**result_body(slot_no=slot_no)).slot_no == slot_no


@pytest.mark.parametrize("slot_no", [0, 5])
def test_slot_number_outside_range_is_rejected(slot_no: int) -> None:
    with pytest.raises(ValidationError):
        SimulationModelResult(**result_body(slot_no=slot_no))


@pytest.mark.parametrize(
    "field, value",
    [
        ("status", "DONE"),
        ("error_type", "BROKEN"),
        ("cost_status", "FREE"),
        ("model_status_at_run", "DELETED"),
        ("json_parse_status", "MAYBE"),
    ],
)
def test_values_outside_the_database_enums_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        SimulationModelResult(**result_body(**{field: value}))


def test_failed_result_keeps_its_error_type() -> None:
    result = SimulationModelResult(
        **result_body(
            status="FAILED",
            error_type="PROVIDER_ERROR",
            cost_status="UNKNOWN",
            cost_usd=None,
            json_parse_status="NOT_EXECUTED",
            schema_validation_status="NOT_EXECUTED",
            missing_required_fields=None,
        )
    )

    assert result.error_type == "PROVIDER_ERROR"


def test_result_carries_the_response_text() -> None:
    # 화면이 모델 칸에 답변을 그대로 그린다. 모델 4개 × 최대 토큰이라 매번 실어도 부담이 작다
    result = SimulationModelResult(**result_body(response_text="답변"))

    assert result.model_dump(mode="json")["response_text"] == "답변"


def test_result_without_a_response_is_null() -> None:
    # 진행 중·실패·취소된 칸은 답변이 없다. 빈 문자열과 구분해 null 로 준다
    assert SimulationModelResult(**result_body()).response_text is None


def test_detail_response_holds_summary_and_results() -> None:
    detail = SimulationDetailResponse(
        summary=summary_body(),
        results=[result_body(slot_no=1), result_body(slot_no=2)],
    )

    dumped = detail.model_dump(mode="json")
    assert dumped["summary"]["simulation_id"] == RUN_ID
    assert [r["slot_no"] for r in dumped["results"]] == [1, 2]
    assert dumped["results"][0]["cost_usd"] == "0.000000348"


def test_detail_response_allows_at_most_four_results() -> None:
    four = [result_body(slot_no=slot) for slot in range(1, 5)]
    assert (
        len(SimulationDetailResponse(summary=summary_body(), results=four).results) == 4
    )

    five = [*four, result_body(slot_no=4)]
    with pytest.raises(ValidationError):
        SimulationDetailResponse(summary=summary_body(), results=five)


def test_detail_response_shows_one_result_per_slot() -> None:
    # 재시도하면 같은 칸에 이전 시도(is_final_attempt=false)가 남는다. 응답에는 마지막 시도만 싣는다
    earlier_attempt = result_body(slot_no=2, status="FAILED", error_type="RATE_LIMIT")
    earlier_attempt |= {"cost_status": "UNKNOWN", "cost_usd": None}
    final_attempt = result_body(slot_no=2)

    with pytest.raises(ValidationError, match="slot_no"):
        SimulationDetailResponse(
            summary=summary_body(), results=[earlier_attempt, final_attempt]
        )


def test_a_slot_result_carries_the_settings_it_was_run_with() -> None:
    config = {"max_tokens": 512, "temperature": 0.2, "reasoning_effort": "high"}

    result = SimulationModelResult(**result_body(execution_config=config))

    assert result.model_dump(mode="json")["execution_config"] == config


def test_a_slot_result_requires_its_settings() -> None:
    body = result_body()
    del body["execution_config"]

    with pytest.raises(ValidationError, match="execution_config"):
        SimulationModelResult(**body)

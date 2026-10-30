import pytest
from pydantic import ValidationError

from app.schemas.simulation_cancel import (
    RequestCancelOutcome,
    SimulationCancelResponse,
)

RUN_ID = "0192a3c4-0000-7000-8000-000000000001"
REQUEST_ID = "0192a3c4-0000-7000-8000-000000000002"


def outcome_body(**overrides: object) -> dict[str, object]:
    """모델 한 칸의 취소 처리 결과. 필요한 값만 덮어써서 쓴다."""
    body: dict[str, object] = {
        "request_id": REQUEST_ID,
        "slot_no": 1,
        "decision": "CANCEL",
        "status": "CANCELLED",
    }
    body.update(overrides)
    return body


def test_outcome_accepts_a_cancelled_slot() -> None:
    dumped = RequestCancelOutcome(**outcome_body()).model_dump(mode="json")

    assert dumped == outcome_body()


def test_repeated_cancel_reports_already_cancelled() -> None:
    # 같은 취소를 두 번 눌러도 오류가 아니라 같은 결과다 (C-08)
    outcome = RequestCancelOutcome(**outcome_body(decision="ALREADY_CANCELLED"))

    assert outcome.status == "CANCELLED"


@pytest.mark.parametrize("status", ["SUCCESS", "FAILED", "TIMEOUT"])
def test_finished_request_reports_its_own_final_status(status: str) -> None:
    # 이미 끝난 결과는 바뀌지 않고, 응답은 그 상태를 그대로 보여 준다 (C-09)
    outcome = RequestCancelOutcome(
        **outcome_body(decision="ALREADY_TERMINAL", status=status)
    )

    assert outcome.status == status


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "SUCCESS"])
def test_cancel_must_show_cancelled_status(status: str) -> None:
    # 취소하면 호출 이력이 즉시 CANCELLED 가 된다. "취소 중" 같은 중간 상태는 없다
    with pytest.raises(ValidationError, match="CANCEL"):
        RequestCancelOutcome(**outcome_body(decision="CANCEL", status=status))


def test_already_cancelled_must_show_cancelled_status() -> None:
    with pytest.raises(ValidationError, match="ALREADY_CANCELLED"):
        RequestCancelOutcome(
            **outcome_body(decision="ALREADY_CANCELLED", status="SUCCESS")
        )


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "CANCELLED"])
def test_already_terminal_cannot_show_an_unfinished_or_cancelled_status(
    status: str,
) -> None:
    with pytest.raises(ValidationError, match="ALREADY_TERMINAL"):
        RequestCancelOutcome(**outcome_body(decision="ALREADY_TERMINAL", status=status))


@pytest.mark.parametrize(
    "field, value",
    [("decision", "DONE"), ("status", "STOPPED"), ("slot_no", 0), ("slot_no", 5)],
)
def test_values_outside_the_contract_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RequestCancelOutcome(**outcome_body(**{field: value}))


def test_response_holds_the_run_status_and_slot_outcomes() -> None:
    response = SimulationCancelResponse(
        simulation_id=RUN_ID,
        status="PARTIAL_SUCCESS",
        results=[
            outcome_body(slot_no=1, decision="ALREADY_TERMINAL", status="SUCCESS"),
            outcome_body(slot_no=2),
        ],
    )

    dumped = response.model_dump(mode="json")
    assert dumped["simulation_id"] == RUN_ID
    assert dumped["status"] == "PARTIAL_SUCCESS"
    assert [r["decision"] for r in dumped["results"]] == [
        "ALREADY_TERMINAL",
        "CANCEL",
    ]


# 모델 하나 취소는 칸 하나, 실행 전체 취소는 칸 2~4개를 담는다. 같은 응답 형식을 쓴다
@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_response_accepts_one_to_four_slots(count: int) -> None:
    results = [outcome_body(slot_no=slot) for slot in range(1, count + 1)]

    response = SimulationCancelResponse(
        simulation_id=RUN_ID, status="CANCELLED", results=results
    )

    assert len(response.results) == count


@pytest.mark.parametrize("count", [0, 5])
def test_response_rejects_no_slots_or_more_than_four(count: int) -> None:
    results = [outcome_body(slot_no=(slot % 4) + 1) for slot in range(count)]

    with pytest.raises(ValidationError):
        SimulationCancelResponse(
            simulation_id=RUN_ID, status="CANCELLED", results=results
        )


def test_response_rejects_duplicate_slots() -> None:
    with pytest.raises(ValidationError, match="slot_no"):
        SimulationCancelResponse(
            simulation_id=RUN_ID,
            status="CANCELLED",
            results=[outcome_body(slot_no=2), outcome_body(slot_no=2)],
        )


def test_cancel_response_carries_no_cost_fields() -> None:
    # 취소된 호출의 비용은 확인 전까지 UNKNOWN 이다. 여기서 0 으로 내보내지 않도록 아예 싣지 않는다
    assert "cost_usd" not in RequestCancelOutcome.model_fields

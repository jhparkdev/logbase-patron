"""app/mock_data/simulations.py 테스트: 모델 비교 실행·결과·호출·원문."""

from collections import Counter

import pytest

from app.mock_data import simulations
from app.mock_data.keys import poc_key
from app.mock_data.members import USERS
from app.mock_data.model_book import ModelBook, build_model_book
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import project_id, service_id
from app.mock_data.period import PERIOD_END, PERIOD_START
from app.mock_data.scenarios import CHANGED_AT, by_code
from app.mock_data.snapshot import load_snapshot
from app.models import RequestStatus, SimulationStatus, UsageOrigin
from app.services.simulation_input import compute_input_hash
from app.services.simulation_json_check import check_json_output
from app.services.simulation_lookup import (
    SIMULATOR_PROJECT_CODE,
    SIMULATOR_SERVICE_CODE,
)
from app.services.simulation_status import compute_overall_status

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}
MEMBERS = {user.user_id: user for user in USERS}
DATA_SUMMARY_ID = by_code("DATA_SUMMARY").scenario_id
RUNS_MIN, RUNS_MAX = 30, 50


@pytest.fixture(scope="module")
def book() -> ModelBook:
    return build_model_book(load_snapshot())


@pytest.fixture(scope="module")
def generated(book: ModelBook) -> simulations.Simulations:
    return simulations.generate_simulations(book)


def _results_by_run(generated: simulations.Simulations) -> dict:
    grouped: dict = {}
    for row in generated.results:
        grouped.setdefault(row["simulation_id"], []).append(row)
    return grouped


def test_same_input_generates_the_same_rows(
    book: ModelBook, generated: simulations.Simulations
) -> None:
    assert simulations.generate_simulations(book) == generated


def test_run_count_matches_the_decided_scale(
    generated: simulations.Simulations,
) -> None:
    assert RUNS_MIN <= len(generated.runs) <= RUNS_MAX


def test_each_run_compares_its_model_count_of_distinct_models(
    generated: simulations.Simulations,
) -> None:
    results = _results_by_run(generated)
    for run in generated.runs:
        slots = results[run["simulation_id"]]
        assert 2 <= run["model_count"] <= 4
        assert len(slots) == run["model_count"]
        assert sorted(r["slot_no"] for r in slots) == list(range(1, len(slots) + 1))
        assert len({r["model_id"] for r in slots}) == len(slots)


def test_models_were_registered_and_not_retired_when_the_run_started(
    generated: simulations.Simulations,
) -> None:
    starts = {run["simulation_id"]: run["started_at"] for run in generated.runs}
    for row in generated.results:
        plan = PLANS[row["model_id"]]
        at = starts[row["simulation_id"]]
        assert plan.registered_at <= at
        assert plan.deactivated_at is None or at < plan.deactivated_at
        expected = (
            "TESTING"
            if plan.activated_at is None or at < plan.activated_at
            else "ACTIVE"
        )
        assert row["model_status_at_run"] == expected


def test_runs_happen_inside_the_period_by_active_members(
    generated: simulations.Simulations,
) -> None:
    for run in generated.runs:
        assert PERIOD_START <= run["requested_at"] <= run["started_at"]
        assert run["completed_at"] <= PERIOD_END
        assert MEMBERS[run["executed_by"]].can_act_at(run["requested_at"])
        assert run["project_id"] == project_id(SIMULATOR_PROJECT_CODE)
        assert run["key_id"] == poc_key().key_id


def test_run_status_follows_the_app_rule(generated: simulations.Simulations) -> None:
    requests = {row["request_id"]: row for row in generated.requests}
    results = _results_by_run(generated)
    for run in generated.runs:
        statuses = [
            requests[r["request_id"]]["status"] for r in results[run["simulation_id"]]
        ]
        assert run["status"] == compute_overall_status(statuses)


def test_statuses_cover_success_partial_failure_and_cancel(
    generated: simulations.Simulations,
) -> None:
    statuses = Counter(run["status"] for run in generated.runs)

    assert (
        statuses[SimulationStatus.SUCCESS]
        > statuses[SimulationStatus.PARTIAL_SUCCESS]
        > 0
    )
    assert statuses[SimulationStatus.CANCELLED] >= 1


def test_requests_are_simulation_calls_on_the_poc_key(
    generated: simulations.Simulations,
) -> None:
    runs = {run["simulation_id"]: run for run in generated.runs}
    for row in generated.requests:
        run = runs[row["simulation_id"]]
        assert row["usage_origin"] == UsageOrigin.SIMULATION
        assert row["service_id"] == service_id(SIMULATOR_SERVICE_CODE)
        assert row["project_id"] == run["project_id"]
        assert row["key_id"] == run["key_id"]
        assert row["executed_by"] == run["executed_by"]
        assert row["input_hash"] == run["input_hash"]
        assert row["routing_policy"]["order"] == [row["requested_provider"]]
        if row["status"] == RequestStatus.SUCCESS:
            assert row["actual_provider"] == row["requested_provider"]


def test_input_hash_uses_the_app_formula(generated: simulations.Simulations) -> None:
    for run in generated.runs:
        assert run["input_hash"] == compute_input_hash(
            run["prompt_text"], run["input_text"]
        )


def test_json_checks_match_the_app_validator(
    generated: simulations.Simulations,
) -> None:
    runs = {run["simulation_id"]: run for run in generated.runs}
    requests = {row["request_id"]: row for row in generated.requests}
    payloads = {row["request_id"]: row for row in generated.payloads}
    for row in generated.results:
        request = requests[row["request_id"]]
        text = payloads[row["request_id"]]["response_text"]
        if request["status"] != RequestStatus.SUCCESS:
            assert text is None
        check = check_json_output(text, runs[row["simulation_id"]]["json_schema"])
        assert row["json_parse_status"] == check.json_parse_status
        assert row["schema_validation_status"] == check.schema_validation_status
        assert row["missing_required_fields"] == check.missing_required_fields


def test_some_json_answers_fail_validation(generated: simulations.Simulations) -> None:
    failed = [r for r in generated.results if r["schema_validation_status"] == "FAILED"]

    assert failed


def test_reruns_copy_the_original_conditions_with_a_new_id(
    generated: simulations.Simulations,
) -> None:
    runs = {run["simulation_id"]: run for run in generated.runs}
    reruns = [
        run for run in generated.runs if run["rerun_of_simulation_id"] is not None
    ]

    assert reruns
    for rerun in reruns:
        original = runs[rerun["rerun_of_simulation_id"]]
        assert original["requested_at"] < rerun["requested_at"]
        for column in ("prompt_text", "input_text", "json_schema", "execution_config"):
            assert rerun[column] == original[column]


def test_data_summary_runs_keep_the_prompt_they_ran_with(
    generated: simulations.Simulations,
) -> None:
    summary_runs = [r for r in generated.runs if r["scenario_id"] == DATA_SUMMARY_ID]
    before = [r for r in summary_runs if r["requested_at"] < CHANGED_AT]
    after = [r for r in summary_runs if r["requested_at"] >= CHANGED_AT]

    assert before and after
    assert all(r["json_schema"] is None for r in before)
    assert all(r["json_schema"] is not None for r in after)


def test_every_request_has_a_payload(generated: simulations.Simulations) -> None:
    assert {r["request_id"] for r in generated.payloads} == {
        r["request_id"] for r in generated.requests
    }

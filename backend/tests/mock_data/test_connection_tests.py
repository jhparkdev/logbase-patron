"""app/mock_data/connection_tests.py 테스트: 모델 연결 테스트 호출."""

import pytest

from app.mock_data import connection_tests as module
from app.mock_data.keys import KEYS
from app.mock_data.model_book import ModelBook, build_model_book
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import project_id, service_id
from app.mock_data.snapshot import load_snapshot
from app.models import RequestStatus, UsageOrigin
from app.services.model_test import TEST_SERVICE_CODE
from app.services.simulation_lookup import SIMULATOR_PROJECT_CODE

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}
KEYS_BY_ID = {key.key_id: key for key in KEYS}


@pytest.fixture(scope="module")
def connection_tests() -> list:
    book: ModelBook = build_model_book(load_snapshot())
    return module.generate_connection_tests(book)


def test_each_model_ends_with_a_successful_test_at_its_planned_time(
    connection_tests: list,
) -> None:
    latest: dict[int, dict] = {}
    for row in sorted(connection_tests, key=lambda r: r["requested_at"]):
        latest[row["model_id"]] = row

    assert latest.keys() == PLANS.keys()
    for model_id, row in latest.items():
        assert row["status"] == RequestStatus.SUCCESS
        assert row["requested_at"] == PLANS[model_id].tested_at


def test_connection_tests_are_run_by_the_registering_member_on_the_poc_key(
    connection_tests: list,
) -> None:
    for row in connection_tests:
        plan = PLANS[row["model_id"]]
        assert row["usage_origin"] == UsageOrigin.SYSTEM_TEST
        assert row["executed_by"] == plan.created_by
        assert row["project_id"] == project_id(SIMULATOR_PROJECT_CODE)
        assert row["service_id"] == service_id(TEST_SERVICE_CODE)
        assert KEYS_BY_ID[row["key_id"]].secret_ref is not None


def test_some_models_needed_a_second_connection_test(connection_tests: list) -> None:
    failed = [row for row in connection_tests if row["status"] != RequestStatus.SUCCESS]

    assert failed

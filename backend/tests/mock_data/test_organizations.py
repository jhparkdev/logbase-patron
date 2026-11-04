"""app/mock_data/organizations.py 테스트: 고객·프로젝트·서비스 기준정보."""

from app.mock_data import organizations
from app.mock_data.period import PERIOD_END, PERIOD_START
from app.models import ProjectType, ServiceType
from app.services.assistant_records import ASSISTANT_SERVICE_CODE
from app.services.model_test import TEST_SERVICE_CODE
from app.services.simulation_lookup import (
    SIMULATOR_PROJECT_CODE,
    SIMULATOR_SERVICE_CODE,
)


def test_customer_codes_and_ids_are_unique() -> None:
    rows = organizations.customer_rows()

    assert len({row["customer_id"] for row in rows}) == len(rows)
    assert len({row["customer_code"] for row in rows}) == len(rows)


def test_every_catalog_row_is_marked_as_mock() -> None:
    rows = (
        organizations.customer_rows()
        + organizations.project_rows()
        + organizations.service_rows()
    )

    assert all(row["is_mock"] is True for row in rows)


def test_only_the_churned_customer_is_inactive() -> None:
    inactive = [c for c in organizations.CUSTOMERS if not c.is_active]

    assert len(inactive) == 1
    assert inactive[0].usage_until is not None
    assert all(c.usage_until is None for c in organizations.CUSTOMERS if c.is_active)


def test_customer_usage_windows_stay_inside_the_mock_period() -> None:
    for customer in organizations.CUSTOMERS:
        assert PERIOD_START <= customer.usage_from < PERIOD_END
        if customer.usage_until is not None:
            assert customer.usage_from < customer.usage_until <= PERIOD_END


def test_customers_use_only_customer_facing_services() -> None:
    facing = {
        s.service_code
        for s in organizations.SERVICES
        if s.service_type == ServiceType.CUSTOMER_FACING
    }

    for customer in organizations.CUSTOMERS:
        assert customer.service_codes
        assert set(customer.service_codes) <= facing


def test_codes_the_app_looks_up_exist_with_the_expected_types() -> None:
    services = {s.service_code: s.service_type for s in organizations.SERVICES}
    projects = {p.project_code: p.project_type for p in organizations.PROJECTS}

    assert services[SIMULATOR_SERVICE_CODE] == ServiceType.PATRON
    assert services[TEST_SERVICE_CODE] == ServiceType.PATRON
    assert services[ASSISTANT_SERVICE_CODE] == ServiceType.PATRON
    assert projects[SIMULATOR_PROJECT_CODE] == ProjectType.POC

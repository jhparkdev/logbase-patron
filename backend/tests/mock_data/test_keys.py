"""app/mock_data/keys.py 테스트: OpenRouter Key 매핑."""

from app.mock_data import keys, organizations
from app.models import KeyEnvironment, KeyOwnerType, KeyStatus
from app.services.simulation_lookup import (
    SIMULATOR_KEY_SECRET_REF,
    SIMULATOR_PROJECT_CODE,
)


def test_key_ids_are_unique() -> None:
    rows = keys.api_key_rows()

    assert len({row["key_id"] for row in rows}) == len(rows)


def test_each_key_has_exactly_the_owner_its_type_requires() -> None:
    # ck_api_keys_owner 제약과 같은 규칙
    for row in keys.api_key_rows():
        if row["owner_type"] == KeyOwnerType.CUSTOMER:
            assert row["customer_id"] is not None and row["project_id"] is None
        else:
            assert row["owner_type"] == KeyOwnerType.PROJECT
            assert row["project_id"] is not None and row["customer_id"] is None


def test_keys_point_only_at_existing_catalog_rows() -> None:
    customer_ids = {c.customer_id for c in organizations.CUSTOMERS}
    project_ids = {p.project_id for p in organizations.PROJECTS}
    service_ids = {s.service_id for s in organizations.SERVICES}

    for row in keys.api_key_rows():
        assert row["customer_id"] is None or row["customer_id"] in customer_ids
        assert row["project_id"] is None or row["project_id"] in project_ids
        assert row["service_id"] is None or row["service_id"] in service_ids


def test_only_the_poc_key_refers_to_a_real_secret() -> None:
    poc_project = organizations.project_id(SIMULATOR_PROJECT_CODE)
    rows = keys.api_key_rows()
    real = [row for row in rows if row["secret_ref"] is not None]

    assert len(real) == 1
    assert real[0]["secret_ref"] == SIMULATOR_KEY_SECRET_REF
    assert real[0]["project_id"] == poc_project
    assert real[0]["is_mock"] is False
    assert all(row["is_mock"] is True for row in rows if row is not real[0])


def test_every_customer_has_a_production_key_for_each_service_it_uses() -> None:
    for customer in organizations.CUSTOMERS:
        for service_code in customer.service_codes:
            key = keys.production_key(customer.customer_id, service_code)
            assert key.environment == KeyEnvironment.PROD


def test_keys_of_the_churned_customer_are_inactive() -> None:
    churned = {c.customer_id for c in organizations.CUSTOMERS if not c.is_active}
    rows = [row for row in keys.api_key_rows() if row["customer_id"] in churned]

    assert rows
    assert all(row["status"] == KeyStatus.INACTIVE for row in rows)

"""관리 명령의 고객·서비스 등록과 고객 Key 매핑을 검증한다."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import APIKey, ChangeLog, Customer, KeyEnvironment, Service, ServiceType
from app.services import usage_catalog
from tests.db_helpers import Factory

SECRET_REF = "NOORIPLUS_2D_MULIT_ANGLE_API_KEY"
RAW_KEY_LIKE = "sk-or-v1-not-a-real-key"


async def _register(session: AsyncSession, **overrides: Any) -> APIKey:
    values = {
        "display_name": "고객 서비스 Key",
        "secret_ref": SECRET_REF,
        "customer_code": "CUST-REAL",
        "service_code": "SVC-REAL",
        "environment": KeyEnvironment.PROD,
        **overrides,
    }
    return await usage_catalog.register_customer_key(session, **values)


@pytest.fixture
async def owner(factory: Factory) -> tuple[Any, Any]:
    customer = await factory.customer(customer_code="CUST-REAL")
    service = await factory.service(
        service_code="SVC-REAL", service_type="CUSTOMER_FACING"
    )
    return customer, service


async def test_create_customer_stores_a_real_row(db_session: AsyncSession) -> None:
    customer = await usage_catalog.create_customer(
        db_session, customer_code="CUST-REAL", name="  실제 고객  "
    )

    assert (customer.customer_code, customer.name) == ("CUST-REAL", "실제 고객")
    # DB 기본값은 mock용 true라 명령으로 만든 실제 행은 구분되어야 한다.
    assert customer.is_mock is False


async def test_create_service_stores_a_real_row(db_session: AsyncSession) -> None:
    service = await usage_catalog.create_service(
        db_session,
        service_code="2D_MULIT_ANGLE",
        name="2D Multi Angle",
        service_type=ServiceType.CUSTOMER_FACING,
    )

    assert service.service_code == "2D_MULIT_ANGLE"
    assert service.service_type == ServiceType.CUSTOMER_FACING
    assert service.is_mock is False


@pytest.mark.parametrize("code", ["", "  ", "lower_case", "한글", "HAS SPACE", "_X"])
async def test_codes_must_be_stable_identifiers(
    db_session: AsyncSession, code: str
) -> None:
    with pytest.raises(usage_catalog.CatalogCommandError):
        await usage_catalog.create_customer(db_session, customer_code=code, name="고객")
    with pytest.raises(usage_catalog.CatalogCommandError):
        await usage_catalog.create_service(
            db_session,
            service_code=code,
            name="서비스",
            service_type=ServiceType.CUSTOMER_FACING,
        )
    assert await db_session.scalar(select(Customer.customer_id)) is None
    assert await db_session.scalar(select(Service.service_id)) is None


async def test_names_must_not_be_blank(db_session: AsyncSession) -> None:
    with pytest.raises(usage_catalog.CatalogCommandError):
        await usage_catalog.create_customer(db_session, customer_code="C1", name="  ")
    with pytest.raises(usage_catalog.CatalogCommandError):
        await usage_catalog.create_service(
            db_session,
            service_code="S1",
            name="  ",
            service_type=ServiceType.CUSTOMER_FACING,
        )


async def test_duplicate_codes_are_refused_and_keep_the_existing_row(
    db_session: AsyncSession,
) -> None:
    await usage_catalog.create_customer(db_session, customer_code="C1", name="처음")
    with pytest.raises(usage_catalog.CatalogCommandError):
        await usage_catalog.create_customer(db_session, customer_code="C1", name="다음")
    assert (await db_session.scalars(select(Customer.name))).all() == ["처음"]

    await usage_catalog.create_service(
        db_session,
        service_code="S1",
        name="처음",
        service_type=ServiceType.CUSTOMER_FACING,
    )
    with pytest.raises(usage_catalog.CatalogCommandError):
        await usage_catalog.create_service(
            db_session,
            service_code="S1",
            name="다음",
            service_type=ServiceType.CUSTOMER_FACING,
        )
    assert (await db_session.scalars(select(Service.name))).all() == ["처음"]


async def test_register_customer_key_links_customer_and_service(
    db_session: AsyncSession, owner: tuple[Any, Any]
) -> None:
    customer, service = owner

    key = await _register(db_session)

    assert key.owner_type == "CUSTOMER"
    assert key.customer_id == customer["customer_id"]
    assert key.project_id is None
    assert key.service_id == service["service_id"]
    # 오타가 있어도 전달받은 환경변수 이름을 그대로 저장한다.
    assert key.secret_ref == SECRET_REF
    assert key.environment == KeyEnvironment.PROD
    assert key.status == "ACTIVE"
    assert key.is_mock is False


async def test_register_customer_key_records_the_mapping_in_change_logs(
    db_session: AsyncSession, owner: tuple[Any, Any]
) -> None:
    customer, service = owner

    key = await _register(db_session)

    log = await db_session.scalar(
        select(ChangeLog).where(ChangeLog.entity_type == "api_keys")
    )
    assert log is not None
    assert log.entity_id == str(key.key_id)
    assert log.action == "CREATE"
    assert log.changes["customer_id"] == {"old": None, "new": customer["customer_id"]}
    assert log.changes["service_id"] == {"old": None, "new": service["service_id"]}
    assert log.changes["secret_ref"] == {"old": None, "new": SECRET_REF}


@pytest.mark.parametrize(
    "secret_ref", [RAW_KEY_LIKE, "SK-OR-V1-ABC", "lower_name", "", " ", "HAS SPACE"]
)
async def test_secret_ref_only_accepts_an_env_var_name_and_never_echoes_input(
    db_session: AsyncSession, owner: tuple[Any, Any], secret_ref: str
) -> None:
    """--secret-ref에 Key 원문을 잘못 넣어도 DB와 오류 문구에 남지 않는다."""
    with pytest.raises(usage_catalog.CatalogCommandError) as caught:
        await _register(db_session, secret_ref=secret_ref)

    assert not secret_ref.strip() or secret_ref not in str(caught.value)
    assert await db_session.scalar(select(APIKey.key_id)) is None
    assert await db_session.scalar(select(ChangeLog.log_id)) is None


@pytest.mark.parametrize(
    "overrides", [{"customer_code": "NO-CUST"}, {"service_code": "NO-SVC"}]
)
async def test_register_customer_key_refuses_unknown_targets(
    db_session: AsyncSession, owner: tuple[Any, Any], overrides: dict[str, str]
) -> None:
    with pytest.raises(usage_catalog.CatalogCommandError):
        await _register(db_session, **overrides)
    assert await db_session.scalar(select(APIKey.key_id)) is None


async def test_register_customer_key_refuses_inactive_targets(
    db_session: AsyncSession, factory: Factory, owner: tuple[Any, Any]
) -> None:
    await factory.customer(customer_code="CUST-OFF", is_active=False)
    await factory.service(
        service_code="SVC-OFF", service_type="CUSTOMER_FACING", is_active=False
    )

    with pytest.raises(usage_catalog.CatalogCommandError):
        await _register(db_session, customer_code="CUST-OFF")
    with pytest.raises(usage_catalog.CatalogCommandError):
        await _register(db_session, service_code="SVC-OFF")
    assert await db_session.scalar(select(APIKey.key_id)) is None


@pytest.mark.parametrize("service_type", ["INTERNAL", "PATRON"])
async def test_customer_key_cannot_be_linked_to_an_internal_service(
    db_session: AsyncSession,
    factory: Factory,
    owner: tuple[Any, Any],
    service_type: str,
) -> None:
    """고객 사용량과 내부·시뮬레이션 비용이 섞이지 않게 한다."""
    await factory.service(service_code="SVC-INNER", service_type=service_type)

    with pytest.raises(usage_catalog.CatalogCommandError):
        await _register(db_session, service_code="SVC-INNER")
    assert await db_session.scalar(select(APIKey.key_id)) is None


async def test_active_secret_ref_cannot_be_registered_twice(
    db_session: AsyncSession, owner: tuple[Any, Any]
) -> None:
    await _register(db_session)

    with pytest.raises(usage_catalog.CatalogCommandError):
        await _register(db_session, display_name="두 번째")

    assert len((await db_session.scalars(select(APIKey.key_id))).all()) == 1


async def test_inactive_secret_ref_can_be_registered_again_as_a_new_row(
    db_session: AsyncSession, factory: Factory, owner: tuple[Any, Any]
) -> None:
    """Key를 교체해도 과거 호출이 가리키는 기존 행은 그대로 남는다."""
    old = await factory.api_key(
        owner_type="CUSTOMER", secret_ref=SECRET_REF, status="INACTIVE"
    )

    key = await _register(db_session)

    assert key.key_id != old["key_id"]
    assert len((await db_session.scalars(select(APIKey.key_id))).all()) == 2

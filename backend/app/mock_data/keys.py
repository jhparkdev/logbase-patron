"""OpenRouter Key 매핑. 실제 Key를 가리키는 것은 시뮬레이터용 PoC Key 하나뿐이고, 나머지는 원문이 없는 Mock Key다."""

from dataclasses import dataclass
from decimal import Decimal

from app.mock_data.organizations import (
    AI_PDP,
    CUSTOMERS,
    FLIPPAGE,
    INTERNAL_TOOL,
    project_id,
    service_id,
)
from app.mock_data.rows import Row
from app.models import KeyEnvironment, KeyOwnerType, KeyStatus, LimitResetPeriod
from app.services.simulation_lookup import (
    SIMULATOR_KEY_SECRET_REF,
    SIMULATOR_PROJECT_CODE,
)

SERVICE_LABELS = {AI_PDP: "AI PDP", FLIPPAGE: "FlipPage"}
# 고객 운영 Key의 월 한도(USD). 사용량이 큰 고객일수록 높게 잡았다.
PROD_LIMIT_USD = {
    1: Decimal(500),
    2: Decimal(300),
    3: Decimal(200),
    4: Decimal(50),
    5: Decimal(100),
    6: Decimal(100),
}
DEV_LIMIT_USD = Decimal(20)
POC_LIMIT_USD = Decimal(50)


@dataclass(frozen=True)
class MockKey:
    key_id: int
    display_name: str
    environment: KeyEnvironment
    customer_id: int | None = None
    project_id: int | None = None
    service_code: str | None = None  # 여러 서비스가 함께 쓰는 Key는 None
    limit_usd: Decimal | None = None
    limit_reset_period: LimitResetPeriod = LimitResetPeriod.MONTHLY
    secret_ref: str | None = None  # 실제 Key가 든 환경변수 이름. Mock Key는 None
    is_active: bool = True


def _build_keys() -> tuple[MockKey, ...]:
    built = [
        MockKey(
            1,
            "PoC 전용 Key",
            KeyEnvironment.TEST,
            project_id=project_id(SIMULATOR_PROJECT_CODE),
            limit_usd=POC_LIMIT_USD,
            limit_reset_period=LimitResetPeriod.NONE,
            secret_ref=SIMULATOR_KEY_SECRET_REF,
        )
    ]
    for customer in CUSTOMERS:
        for code in customer.service_codes:
            built.append(
                MockKey(
                    len(built) + 1,
                    f"{customer.name} {SERVICE_LABELS[code]} 운영 Key",
                    KeyEnvironment.PROD,
                    customer_id=customer.customer_id,
                    service_code=code,
                    limit_usd=PROD_LIMIT_USD[customer.customer_id],
                    is_active=customer.is_active,
                )
            )
        built.append(
            MockKey(
                len(built) + 1,
                f"{customer.name} 개발 Key",
                KeyEnvironment.DEV,
                customer_id=customer.customer_id,
                limit_usd=DEV_LIMIT_USD,
                is_active=customer.is_active,
            )
        )
    for name, project_code, code in (
        ("AI PDP 고도화 개발 Key", "PRJ-PDP-DEV", AI_PDP),
        ("내부 개발 도구 Key", "PRJ-PDP-DEV", INTERNAL_TOOL),
        ("상세페이지 리뉴얼 Key", "PRJ-CUST-RENEWAL", FLIPPAGE),
    ):
        built.append(
            MockKey(
                len(built) + 1,
                name,
                KeyEnvironment.DEV,
                project_id=project_id(project_code),
                service_code=code,
                limit_usd=DEV_LIMIT_USD,
            )
        )
    return tuple(built)


KEYS = _build_keys()


def production_key(customer_id: int, service_code: str) -> MockKey:
    return next(
        k
        for k in KEYS
        if k.customer_id == customer_id
        and k.service_code == service_code
        and k.environment == KeyEnvironment.PROD
    )


def project_key(project_code: str, service_code: str) -> MockKey:
    project = project_id(project_code)
    return next(
        k for k in KEYS if k.project_id == project and k.service_code == service_code
    )


def poc_key() -> MockKey:
    return next(k for k in KEYS if k.secret_ref == SIMULATOR_KEY_SECRET_REF)


def api_key_rows() -> list[Row]:
    return [
        {
            "key_id": k.key_id,
            "display_name": k.display_name,
            "secret_ref": k.secret_ref,
            "key_fingerprint": None,
            "workspace_ref": None,
            "owner_type": KeyOwnerType.CUSTOMER
            if k.customer_id
            else KeyOwnerType.PROJECT,
            "customer_id": k.customer_id,
            "project_id": k.project_id,
            "service_id": service_id(k.service_code) if k.service_code else None,
            "environment": k.environment,
            "status": KeyStatus.ACTIVE if k.is_active else KeyStatus.INACTIVE,
            "limit_usd": k.limit_usd,
            "limit_reset_period": k.limit_reset_period,
            "is_mock": k.secret_ref is None,
        }
        for k in KEYS
    ]

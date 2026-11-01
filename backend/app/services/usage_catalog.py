"""관리 CLI의 고객·서비스 등록과 고객 Key 매핑.

Key 원문은 다루지 않는다. 환경변수 이름만 받아 저장하고 그 값은 읽지 않는다.
"""

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    APIKey,
    ChangeAction,
    ChangeLog,
    Customer,
    KeyEnvironment,
    KeyOwnerType,
    KeyStatus,
    Service,
    ServiceType,
)

CODE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]*")
# Key 원문을 잘못 넣어도 저장되지 않도록 환경변수 이름 형식만 받는다.
SECRET_REF_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*")
KEY_ENTITY_TYPE = "api_keys"
KEY_REGISTER_REASON = "관리 명령 key-register로 Key 매핑 등록"


class CatalogCommandError(Exception):
    """관리 명령에서 입력값이나 내부 정보를 노출하지 않고 보여 줄 오류."""


def _require_code(code: str, *, label: str) -> str:
    if CODE_PATTERN.fullmatch(code) is None:
        raise CatalogCommandError(
            f"{label}는 영문 대문자·숫자·밑줄·하이픈으로 입력하세요."
        )
    return code


def _require_text(value: str, *, label: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise CatalogCommandError(f"{label}을 입력하세요.")
    return stripped


async def create_customer(
    session: AsyncSession, *, customer_code: str, name: str
) -> Customer:
    customer = Customer(
        customer_code=_require_code(customer_code, label="고객 코드"),
        name=_require_text(name, label="고객 이름"),
        is_active=True,
        # DB 기본값은 mock용 true라 관리 명령으로 만든 실제 행은 명시적으로 구분한다.
        is_mock=False,
    )
    session.add(customer)
    await _commit_new_row(session, duplicate_message="이미 사용 중인 고객 코드입니다.")
    return customer


async def create_service(
    session: AsyncSession, *, service_code: str, name: str, service_type: ServiceType
) -> Service:
    service = Service(
        service_code=_require_code(service_code, label="서비스 코드"),
        name=_require_text(name, label="서비스 이름"),
        service_type=service_type.value,
        is_active=True,
        is_mock=False,
    )
    session.add(service)
    await _commit_new_row(
        session, duplicate_message="이미 사용 중인 서비스 코드입니다."
    )
    return service


async def register_customer_key(
    session: AsyncSession,
    *,
    display_name: str,
    secret_ref: str,
    customer_code: str,
    service_code: str,
    environment: KeyEnvironment,
) -> APIKey:
    """고객 서비스 전용 Key를 연결한다. Key를 교체할 때도 기존 행은 두고 새 행을 추가한다."""
    display_name = _require_text(display_name, label="Key 표시 이름")
    if SECRET_REF_PATTERN.fullmatch(secret_ref) is None:
        raise CatalogCommandError("--secret-ref에는 환경변수 이름만 입력하세요.")
    customer_id = await session.scalar(
        select(Customer.customer_id).where(
            Customer.customer_code == customer_code, Customer.is_active
        )
    )
    if customer_id is None:
        raise CatalogCommandError("사용 중인 고객을 찾을 수 없습니다.")
    # 고객 사용량과 내부·시뮬레이션 비용이 섞이지 않도록 고객용 서비스만 연결한다.
    service_id = await session.scalar(
        select(Service.service_id).where(
            Service.service_code == service_code,
            Service.is_active,
            Service.service_type == ServiceType.CUSTOMER_FACING.value,
        )
    )
    if service_id is None:
        raise CatalogCommandError("사용 중인 고객용 서비스를 찾을 수 없습니다.")
    already_used = await session.scalar(
        select(APIKey.key_id).where(
            APIKey.secret_ref == secret_ref,
            APIKey.status == KeyStatus.ACTIVE.value,
        )
    )
    if already_used is not None:
        raise CatalogCommandError("이미 사용 중인 환경변수 이름입니다.")

    key = APIKey(
        display_name=display_name,
        secret_ref=secret_ref,
        owner_type=KeyOwnerType.CUSTOMER.value,
        customer_id=customer_id,
        service_id=service_id,
        environment=environment.value,
        status=KeyStatus.ACTIVE.value,
        is_mock=False,
    )
    session.add(key)
    await session.flush()
    session.add(
        ChangeLog(
            entity_type=KEY_ENTITY_TYPE,
            entity_id=str(key.key_id),
            action=ChangeAction.CREATE.value,
            changes={
                "display_name": {"old": None, "new": display_name},
                "secret_ref": {"old": None, "new": secret_ref},
                "customer_id": {"old": None, "new": customer_id},
                "service_id": {"old": None, "new": service_id},
                "environment": {"old": None, "new": environment.value},
            },
            reason=KEY_REGISTER_REASON,
        )
    )
    await session.commit()
    return key


async def _commit_new_row(session: AsyncSession, *, duplicate_message: str) -> None:
    try:
        await session.commit()
    except IntegrityError:
        # 동시에 같은 코드를 등록해도 DB 고유 제약으로 거절하고, 실패한 트랜잭션을 정리한다.
        await session.rollback()
        raise CatalogCommandError(duplicate_message) from None

"""관리 CLI의 구성원별 Command Code Key 이름 등록.

Key 원문은 다루지 않는다. 환경변수 이름(secret_ref)만 받아 저장하고 그 값은 읽지 않는다.
"""

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommandCodeKey
from app.services.usage_catalog import CatalogCommandError

# DB 제약(command_code_keys.secret_ref)과 같은 형식이다. Key 원문을 잘못 넣어도 저장되지 않는다.
SECRET_REF_PATTERN = re.compile(r"COMMAND_CODE_KEY_[A-Z0-9_]+")
SECRET_REF_MESSAGE = (
    "--secret-ref에는 COMMAND_CODE_KEY_로 시작하는 환경변수 이름만 입력하세요."
)
MEMBER_DUPLICATE_MESSAGE = "이미 사용 중인 구성원 이름입니다."
SECRET_REF_DUPLICATE_MESSAGE = "이미 사용 중인 환경변수 이름입니다."


async def register_member(
    session: AsyncSession, *, member_name: str, secret_ref: str
) -> CommandCodeKey:
    """구성원 한 명과 그 Key의 환경변수 이름을 연결한다. 사용 중인 구성원 이름은 겹칠 수 없다."""
    member_name = member_name.strip()
    if not member_name:
        raise CatalogCommandError("구성원 이름을 입력하세요.")
    # 잘못 넣은 값이 Key 원문일 수 있어 오류 문구에 입력값을 넣지 않는다.
    if SECRET_REF_PATTERN.fullmatch(secret_ref) is None:
        raise CatalogCommandError(SECRET_REF_MESSAGE)
    member_taken = await session.scalar(
        select(CommandCodeKey.command_code_key_id).where(
            CommandCodeKey.member_name == member_name, CommandCodeKey.is_active
        )
    )
    if member_taken is not None:
        raise CatalogCommandError(MEMBER_DUPLICATE_MESSAGE)
    # 사용을 멈춘 행의 이름도 다시 쓸 수 없다(secret_ref는 전체에서 고유하다).
    ref_taken = await session.scalar(
        select(CommandCodeKey.command_code_key_id).where(
            CommandCodeKey.secret_ref == secret_ref
        )
    )
    if ref_taken is not None:
        raise CatalogCommandError(SECRET_REF_DUPLICATE_MESSAGE)

    key = CommandCodeKey(member_name=member_name, secret_ref=secret_ref, is_active=True)
    session.add(key)
    try:
        await session.commit()
    except IntegrityError:
        # 동시에 같은 값을 등록해도 DB 고유 제약으로 거절하고, 실패한 트랜잭션을 정리한다.
        await session.rollback()
        raise CatalogCommandError(MEMBER_DUPLICATE_MESSAGE) from None
    return key

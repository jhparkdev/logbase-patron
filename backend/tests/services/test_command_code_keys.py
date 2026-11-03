"""services/command_code_keys.py 테스트. 구성원과 Key 이름(secret_ref)을 연결해 저장한다.

Key 원문은 다루지 않는다. 이름만 받아 저장하고 그 값은 읽지 않는다.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommandCodeKey
from app.services import command_code_keys
from app.services.usage_catalog import CatalogCommandError
from tests.db_helpers import Factory

SECRET_REF = "COMMAND_CODE_KEY_HONG"
# 테스트용 가짜 값. Key 원문을 잘못 넣었을 때 저장되거나 메시지에 드러나는지 찾을 표식이다
RAW_KEY_LIKE = "user_abc123-not-a-real-key"


async def _count(session: AsyncSession) -> int:
    total = await session.scalar(select(func.count()).select_from(CommandCodeKey))
    return total or 0


async def test_구성원과_Key_이름을_저장한다(db_session: AsyncSession) -> None:
    key = await command_code_keys.register_member(
        db_session, member_name="홍길동", secret_ref=SECRET_REF
    )

    assert (key.member_name, key.secret_ref) == ("홍길동", SECRET_REF)
    assert key.is_active is True
    assert key.command_code_key_id is not None


async def test_구성원_이름의_앞뒤_공백은_지우고_저장한다(
    db_session: AsyncSession,
) -> None:
    key = await command_code_keys.register_member(
        db_session, member_name="  홍길동  ", secret_ref=SECRET_REF
    )

    assert key.member_name == "홍길동"


@pytest.mark.parametrize("member_name", ["", "   "])
async def test_빈_구성원_이름은_거절한다(
    db_session: AsyncSession, member_name: str
) -> None:
    with pytest.raises(CatalogCommandError):
        await command_code_keys.register_member(
            db_session, member_name=member_name, secret_ref=SECRET_REF
        )

    assert await _count(db_session) == 0


@pytest.mark.parametrize(
    "secret_ref",
    [
        RAW_KEY_LIKE,
        "",
        "COMMAND_CODE_KEY_",
        "COMMAND_CODE_KEY_hong",
        "command_code_key_hong",
        "OPENROUTER_API_KEY",
        "COMMAND_CODE_KEY_HONG ",
        "COMMAND_CODE_KEY_홍길동",
    ],
)
async def test_정해진_형식이_아닌_Key_이름은_거절한다(
    db_session: AsyncSession, secret_ref: str
) -> None:
    with pytest.raises(CatalogCommandError):
        await command_code_keys.register_member(
            db_session, member_name="홍길동", secret_ref=secret_ref
        )

    assert await _count(db_session) == 0


async def test_Key_원문을_넣으면_오류_문구에_되돌려_보여_주지_않는다(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(CatalogCommandError) as error:
        await command_code_keys.register_member(
            db_session, member_name="홍길동", secret_ref=RAW_KEY_LIKE
        )

    assert RAW_KEY_LIKE not in str(error.value)


async def test_사용_중인_구성원_이름은_다시_등록할_수_없다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.command_code_key(
        member_name="홍길동", secret_ref="COMMAND_CODE_KEY_A"
    )

    with pytest.raises(CatalogCommandError):
        await command_code_keys.register_member(
            db_session, member_name="홍길동", secret_ref="COMMAND_CODE_KEY_B"
        )

    assert await _count(db_session) == 1


async def test_이미_쓰는_Key_이름은_다른_구성원에게_연결할_수_없다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.command_code_key(member_name="홍길동", secret_ref=SECRET_REF)

    with pytest.raises(CatalogCommandError):
        await command_code_keys.register_member(
            db_session, member_name="김철수", secret_ref=SECRET_REF
        )

    assert await _count(db_session) == 1


async def test_사용을_멈춘_구성원은_새_Key로_다시_등록할_수_있다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.command_code_key(
        member_name="홍길동", secret_ref="COMMAND_CODE_KEY_OLD", is_active=False
    )

    key = await command_code_keys.register_member(
        db_session, member_name="홍길동", secret_ref="COMMAND_CODE_KEY_NEW"
    )

    assert key.is_active is True
    assert await _count(db_session) == 2

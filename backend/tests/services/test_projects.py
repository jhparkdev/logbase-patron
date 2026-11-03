"""프로젝트 등록 테스트. 이름이 같은 사용 중 프로젝트는 만들지 않고, 만든 것은 변경 이력(change_logs)에 남긴다."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog, Project, ProjectType
from app.services.projects import (
    ProjectDuplicateError,
    available_code,
    create_project,
)
from tests.db_helpers import Factory


@pytest.fixture
async def user_id(factory: Factory) -> int:
    return (await factory.user())["user_id"]


def new_values(**values: Any) -> dict[str, Any]:
    """등록에 필요한 값. 종류와 코드는 기본이 비어 있다(종류는 서비스가 기본값을 쓴다)."""
    return {
        "name": "새 프로젝트",
        "project_type": ProjectType.INTERNAL_DEV,
        "project_code": None,
        **values,
    }


async def stored_of(session: AsyncSession, project_id: int) -> Project:
    session.expire_all()
    row = await session.get(Project, project_id)
    assert row is not None
    return row


async def project_count(session: AsyncSession) -> int:
    session.expire_all()
    return len(list(await session.scalars(select(Project))))


async def logs_of(session: AsyncSession, project_id: int) -> list[ChangeLog]:
    rows = await session.scalars(
        select(ChangeLog).where(
            ChangeLog.entity_type == "projects",
            ChangeLog.entity_id == str(project_id),
        )
    )
    return list(rows)


# ---------------------------------------------------------------
# 등록
# ---------------------------------------------------------------
async def test_등록하면_사용_중이고_모의_데이터가_아닌_프로젝트로_저장한다(
    db_session: AsyncSession, user_id: int
) -> None:
    created = await create_project(db_session, new_values(), user_id)

    stored = await stored_of(db_session, created.project_id)
    assert (stored.name, stored.project_type) == ("새 프로젝트", "INTERNAL_DEV")
    assert (stored.is_active, stored.is_mock) == (True, False)


async def test_코드를_주지_않으면_프로젝트_번호로_코드를_만든다(
    db_session: AsyncSession, user_id: int
) -> None:
    created = await create_project(db_session, new_values(), user_id)

    assert created.project_code == f"PRJ-{created.project_id:06d}"
    stored = await stored_of(db_session, created.project_id)
    assert stored.project_code == created.project_code


async def test_코드를_주면_그_코드로_저장한다(
    db_session: AsyncSession, user_id: int
) -> None:
    created = await create_project(
        db_session, new_values(project_code="PRJ-CUSTOM-1"), user_id
    )

    assert created.project_code == "PRJ-CUSTOM-1"


async def test_종류를_주면_그_종류로_저장한다(
    db_session: AsyncSession, user_id: int
) -> None:
    created = await create_project(
        db_session, new_values(project_type=ProjectType.POC), user_id
    )

    assert created.project_type == ProjectType.POC
    stored = await stored_of(db_session, created.project_id)
    assert stored.project_type == "POC"


async def test_등록하면_생성_이력_한_건을_남긴다(
    db_session: AsyncSession, user_id: int
) -> None:
    created = await create_project(db_session, new_values(), user_id)

    logs = await logs_of(db_session, created.project_id)
    assert len(logs) == 1
    log = logs[0]
    assert log.action == "CREATE"
    assert (log.reason, log.changed_by) == ("프로젝트 등록", user_id)
    assert log.changes == {
        "project_code": {"old": None, "new": created.project_code},
        "name": {"old": None, "new": "새 프로젝트"},
        "project_type": {"old": None, "new": "INTERNAL_DEV"},
    }


# ---------------------------------------------------------------
# 이름이 같은 프로젝트
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    ["my project", "MY PROJECT", "  My Project  ", "My   Project"],
    ids=["소문자", "대문자", "앞뒤 공백", "가운데 공백이 여러 개"],
)
async def test_띄어쓰기와_대소문자만_다른_이름은_중복이다(
    db_session: AsyncSession, user_id: int, name: str
) -> None:
    first = await create_project(db_session, new_values(name="My Project"), user_id)

    with pytest.raises(ProjectDuplicateError) as raised:
        await create_project(db_session, new_values(name=name), user_id)

    assert raised.value.existing.project_id == first.project_id
    assert await project_count(db_session) == 1
    assert len(await logs_of(db_session, first.project_id)) == 1


@pytest.mark.parametrize("name", ["My-Project", "MyProject", "My Project 2"])
async def test_글자가_다르면_다른_프로젝트로_등록한다(
    db_session: AsyncSession, user_id: int, name: str
) -> None:
    await create_project(db_session, new_values(name="My Project"), user_id)

    created = await create_project(db_session, new_values(name=name), user_id)

    assert created.name == name


async def test_사용_중이_아닌_프로젝트와_같은_이름은_등록할_수_있다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    await factory.project(name="같은 이름", is_active=False)

    created = await create_project(db_session, new_values(name="같은 이름"), user_id)

    assert created.name == "같은 이름"


async def test_중복이면_기존_프로젝트의_정보를_돌려준다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    existing = await factory.project(name="있는 프로젝트", project_type="POC")

    with pytest.raises(ProjectDuplicateError) as raised:
        await create_project(db_session, new_values(name="있는 프로젝트"), user_id)

    found = raised.value.existing
    assert found.project_id == existing["project_id"]
    assert found.project_code == existing["project_code"]
    assert found.project_type == ProjectType.POC


# ---------------------------------------------------------------
# 코드
# ---------------------------------------------------------------
async def test_이미_있는_코드를_주면_그_프로젝트를_중복으로_알린다(
    db_session: AsyncSession, factory: Factory, user_id: int
) -> None:
    existing = await factory.project(project_code="TAKEN-1")

    with pytest.raises(ProjectDuplicateError) as raised:
        await create_project(
            db_session, new_values(name="다른 이름", project_code="TAKEN-1"), user_id
        )

    assert raised.value.existing.project_id == existing["project_id"]
    assert await project_count(db_session) == 1


async def test_만든_코드가_이미_쓰이면_번호를_붙여_피한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.project(project_code="PRJ-000007")
    assert await available_code(db_session, 8) == "PRJ-000008"

    assert await available_code(db_session, 7) == "PRJ-000007-2"
    await factory.project(project_code="PRJ-000007-2")
    assert await available_code(db_session, 7) == "PRJ-000007-3"

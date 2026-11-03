"""프로젝트(P-02) 등록. 삭제는 없다: 쓰지 않는 프로젝트는 is_active를 끈다.

이름이 같은 사용 중 프로젝트는 만들지 않는다. 사용자는 이름만 적으므로 띄어쓰기와 대소문자만
다른 같은 프로젝트가 두 번 생기지 않게 한다. DB에는 이름의 유일 제약이 없어서, 같은 순간에 같은
이름이 두 번 들어오면 둘 다 만들어질 수 있다(PoC에서는 받아들인다).
"""

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeAction, ChangeLog, Project, ProjectType
from app.schemas.project import ProjectRead

ENTITY_TYPE = "projects"
CREATE_REASON = "프로젝트 등록"
CODE_PREFIX = "PRJ-"
CODE_NUMBER_DIGITS = 6
# 이름은 앞뒤 공백을 없애고 가운데 공백은 하나로 모은 뒤 소문자로 비교한다
WHITESPACE_RUN = r"\s+"
LOGGED_COLUMNS = ("project_code", "name", "project_type")


class ProjectDuplicateError(ValueError):
    """같은 이름(또는 같은 코드)의 프로젝트가 이미 있다. existing은 그 프로젝트다."""

    def __init__(self, existing: ProjectRead) -> None:
        super().__init__("이미 있는 프로젝트다")
        self.existing = existing


def normalize_name(name: str) -> str:
    return " ".join(name.split()).lower()


def _read(project: Project) -> ProjectRead:
    return ProjectRead(
        project_id=project.project_id,
        project_code=project.project_code,
        name=project.name,
        project_type=project.project_type,
    )


async def _find_by_name(session: AsyncSession, name: str) -> Project | None:
    # 공백(탭 포함)을 하나로 모은 뒤 앞뒤를 지우고 소문자로 만든다. normalize_name과 같은 규칙이다
    normalized = func.lower(
        func.btrim(func.regexp_replace(Project.name, WHITESPACE_RUN, " ", "g"))
    )
    return await session.scalar(
        select(Project)
        .where(Project.is_active, normalized == normalize_name(name))
        .order_by(Project.project_id)
        .limit(1)
    )


async def _find_by_code(session: AsyncSession, code: str) -> Project | None:
    return await session.scalar(select(Project).where(Project.project_code == code))


async def available_code(session: AsyncSession, project_id: int) -> str:
    """프로젝트 번호로 만든 코드. 이미 쓰이고 있으면 -2, -3을 붙여 피한다."""
    base = f"{CODE_PREFIX}{project_id:0{CODE_NUMBER_DIGITS}d}"
    candidate = base
    suffix = 2
    while await _find_by_code(session, candidate) is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


async def create_project(
    session: AsyncSession, values: Mapping[str, Any], user_id: int
) -> ProjectRead:
    """프로젝트를 사용 중(is_active)이고 모의 데이터가 아닌 것으로 등록한다. values는 ProjectCreate의 필드와 같다."""
    existing = await _find_by_name(session, values["name"])
    if existing is not None:
        raise ProjectDuplicateError(_read(existing))
    given_code = values["project_code"]
    if given_code is not None:
        taken = await _find_by_code(session, given_code)
        if taken is not None:
            raise ProjectDuplicateError(_read(taken))

    project = Project(
        # 코드를 안 주면 번호를 알 수 있을 때 바꾸므로 지금은 겹치지 않는 임시 값을 둔다
        project_code=given_code or f"TMP-{uuid4().hex}",
        name=values["name"],
        project_type=ProjectType(values["project_type"]).value,
        is_active=True,
        is_mock=False,
    )
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as error:
        # 위의 코드 확인과 저장 사이에 같은 코드가 먼저 들어간 경우다
        await session.rollback()
        taken = await _find_by_code(session, given_code) if given_code else None
        if taken is None:
            raise
        raise ProjectDuplicateError(_read(taken)) from error
    if given_code is None:
        project.project_code = await available_code(session, project.project_id)
        await session.flush()
    session.add(
        ChangeLog(
            entity_type=ENTITY_TYPE,
            entity_id=str(project.project_id),
            action=ChangeAction.CREATE.value,
            changes={
                column: {"old": None, "new": getattr(project, column)}
                for column in LOGGED_COLUMNS
            },
            reason=CREATE_REASON,
            changed_by=user_id,
        )
    )
    await session.commit()
    return _read(project)

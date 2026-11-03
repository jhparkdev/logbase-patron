"""POST /api/projects 테스트. 구독료 폼에서 새 프로젝트를 만들 때 쓰는 프로젝트 등록을 확인한다."""

from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeLog
from tests.db_helpers import Factory

BASE = "/api/projects"
SUBSCRIPTION_OPTIONS = "/api/subscriptions/options"
INTERNAL_OPTIONS = "/api/usage/internal/options"


@pytest.fixture(autouse=True)
async def admin(factory: Factory) -> int:
    """등록자로 기록되는 첫 활성 계정(DevUserDep)."""
    return (await factory.user())["user_id"]


# ---------------------------------------------------------------
# 등록
# ---------------------------------------------------------------
async def test_이름만_보내면_201과_만들어진_프로젝트를_돌려준다(
    client: AsyncClient,
) -> None:
    response = await client.post(BASE, json={"name": "새 프로젝트"})

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert set(body) == {"project_id", "project_code", "name", "project_type"}
    assert body["name"] == "새 프로젝트"
    assert body["project_type"] == "INTERNAL_DEV"
    assert body["project_code"] == f"PRJ-{body['project_id']:06d}"


async def test_이름의_앞뒤_공백은_지우고_저장한다(client: AsyncClient) -> None:
    response = await client.post(BASE, json={"name": "  공백 있는 이름  "})

    assert response.json()["name"] == "공백 있는 이름"


async def test_코드와_종류를_보내면_그_값으로_저장한다(client: AsyncClient) -> None:
    body = {"name": "시험 프로젝트", "project_type": "POC", "project_code": "POC-1"}

    response = await client.post(BASE, json=body)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["project_type"] == "POC"
    assert response.json()["project_code"] == "POC-1"


async def test_이름이_다른_두_프로젝트는_코드가_겹치지_않는다(
    client: AsyncClient,
) -> None:
    first = (await client.post(BASE, json={"name": "하나"})).json()
    second = (await client.post(BASE, json={"name": "둘"})).json()

    assert first["project_code"] != second["project_code"]
    assert first["project_id"] != second["project_id"]


async def test_등록하면_생성_이력이_남는다(
    client: AsyncClient, db_session: AsyncSession, admin: int
) -> None:
    created = (await client.post(BASE, json={"name": "이력 확인"})).json()

    logs = list(
        await db_session.scalars(
            select(ChangeLog).where(
                ChangeLog.entity_type == "projects",
                ChangeLog.entity_id == str(created["project_id"]),
            )
        )
    )
    assert [(log.action, log.changed_by) for log in logs] == [("CREATE", admin)]


async def test_등록한_프로젝트가_두_선택_목록에_바로_보인다(
    client: AsyncClient,
) -> None:
    name = "바로 보이는 프로젝트"
    project_id = (await client.post(BASE, json={"name": name})).json()["project_id"]

    subscription = (await client.get(SUBSCRIPTION_OPTIONS)).json()["projects"]
    internal = (await client.get(INTERNAL_OPTIONS)).json()["projects"]

    assert {"project_id": project_id, "name": name} in subscription
    assert {"id": project_id, "name": name} in internal


# ---------------------------------------------------------------
# 이름이 같은 프로젝트
# ---------------------------------------------------------------
async def test_같은_이름은_409이고_기존_프로젝트를_돌려준다(
    client: AsyncClient,
) -> None:
    first = (await client.post(BASE, json={"name": "중복 확인"})).json()

    response = await client.post(BASE, json={"name": "중복 확인"})

    assert response.status_code == status.HTTP_409_CONFLICT
    body = response.json()
    assert body["code"] == "PROJECT_DUPLICATE"
    assert body["message"]
    assert body["existing"] == first


@pytest.mark.parametrize(
    "name",
    ["my project", "MY PROJECT", "  My Project  ", "My   Project"],
    ids=["소문자", "대문자", "앞뒤 공백", "가운데 공백이 여러 개"],
)
async def test_띄어쓰기와_대소문자만_다른_이름도_409이다(
    client: AsyncClient, name: str
) -> None:
    first = (await client.post(BASE, json={"name": "My Project"})).json()

    response = await client.post(BASE, json={"name": name})

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["existing"]["project_id"] == first["project_id"]


async def test_사용_중이_아닌_프로젝트와_같은_이름은_등록된다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.project(name="쉬는 프로젝트", is_active=False)

    response = await client.post(BASE, json={"name": "쉬는 프로젝트"})

    assert response.status_code == status.HTTP_201_CREATED


async def test_이미_있는_코드를_보내면_409이고_그_프로젝트를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    existing = await factory.project(project_code="TAKEN-1")

    response = await client.post(
        BASE, json={"name": "다른 이름", "project_code": "TAKEN-1"}
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["existing"]["project_id"] == existing["project_id"]


# ---------------------------------------------------------------
# 입력과 권한
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "가" * 101},
        {"name": None},
        {"name": "이름", "project_type": "UNKNOWN"},
        {"name": "이름", "project_code": "소문자-code"},
        {"name": "이름", "project_code": ""},
        {"name": "이름", "project_code": "A" * 51},
        {"name": "이름", "is_mock": True},
    ],
    ids=[
        "이름 없음",
        "빈 이름",
        "공백뿐인 이름",
        "101자 이름",
        "이름이 null",
        "모르는 종류",
        "허용하지 않는 코드 모양",
        "빈 코드",
        "51자 코드",
        "모르는 항목",
    ],
)
async def test_잘못된_본문은_422이고_아무것도_만들지_않는다(
    client: AsyncClient, db_session: AsyncSession, body: dict[str, Any]
) -> None:
    before = await db_session.scalar(text("SELECT count(*) FROM projects"))

    response = await client.post(BASE, json=body)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert await db_session.scalar(text("SELECT count(*) FROM projects")) == before


async def test_활성_계정이_없으면_401이다(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await db_session.execute(text("UPDATE users SET is_active = false"))

    response = await client.post(BASE, json={"name": "새 프로젝트"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_허용하지_않는_Origin의_등록은_거절한다(client: AsyncClient) -> None:
    response = await client.post(
        BASE, json={"name": "새 프로젝트"}, headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"

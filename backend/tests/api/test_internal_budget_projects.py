"""GET /api/usage/internal/projects 테스트. 내부 AI 예산 관리(P-02)의 프로젝트별 예산 표를 확인한다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.db_helpers import Factory
from tests.internal_budget_helpers import internal_call

PROJECTS = "/api/usage/internal/projects"
OCTOBER = {"month": "2026-10"}


async def project_with_usage(
    factory: Factory, name: str, cost: str, budget: str | None = None
) -> int:
    project = await factory.project(name=name)
    if budget is not None:
        await factory.budget(
            project_id=project["project_id"], monthly_amount_usd=Decimal(budget)
        )
    await internal_call(
        factory, project_id=project["project_id"], cost_usd=Decimal(cost)
    )
    return project["project_id"]


def names(body: dict[str, Any]) -> list[str]:
    return [item["project_name"] for item in body["items"]]


async def test_프로젝트별_예산_사용액_상태를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    await factory.budget(project_id=project["project_id"], monthly_amount_usd=100)
    await internal_call(factory, project_id=project["project_id"], cost_usd=Decimal(85))
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1),
        amount=Decimal(5),
        project_id=project["project_id"],
    )

    response = await client.get(PROJECTS, params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 10
    item = body["items"][0]
    assert item["project_id"] == project["project_id"]
    assert item["project_name"] == "알파"
    assert Decimal(item["monthly_amount_usd"]) == 100
    assert Decimal(item["used_usd"]) == 90
    assert Decimal(item["usage_pct"]) == 90
    assert item["status"] == "WARNING"
    assert item["unknown_cost_count"] == 0


async def test_예산이_없는_프로젝트는_예산과_사용률이_null이고_미설정이다(
    client: AsyncClient, factory: Factory
) -> None:
    await project_with_usage(factory, "예산 없음", "3")

    item = (await client.get(PROJECTS, params=OCTOBER)).json()["items"][0]

    assert item["monthly_amount_usd"] is None
    assert item["usage_pct"] is None
    assert item["status"] == "UNSET"
    assert Decimal(item["used_usd"]) == 3


async def test_금액은_문자열이고_작은_값도_지수_표기가_아니다(
    client: AsyncClient, factory: Factory
) -> None:
    await project_with_usage(factory, "작은 비용", "0.00000003")

    item = (await client.get(PROJECTS, params=OCTOBER)).json()["items"][0]

    assert isinstance(item["used_usd"], str)
    assert "e" not in item["used_usd"].lower()
    assert Decimal(item["used_usd"]) == Decimal("0.00000003")


async def test_기본_정렬은_사용률이_높은_순서이고_예산이_없으면_맨_뒤다(
    client: AsyncClient, factory: Factory
) -> None:
    # 사용액은 정상이 더 크지만 예산을 넘긴 프로젝트가 위에 와야 한다.
    await project_with_usage(factory, "정상", "1000", budget="5000")
    await project_with_usage(factory, "미설정", "700")
    await project_with_usage(factory, "초과", "150", budget="100")

    body = (await client.get(PROJECTS, params=OCTOBER)).json()

    assert names(body) == ["초과", "정상", "미설정"]


async def test_예산이_없는_프로젝트끼리는_사용액이_큰_순서이다(
    client: AsyncClient, factory: Factory
) -> None:
    await project_with_usage(factory, "작음", "1")
    await project_with_usage(factory, "큼", "9")
    await project_with_usage(factory, "중간", "5")

    body = (await client.get(PROJECTS, params=OCTOBER)).json()

    assert names(body) == ["큼", "중간", "작음"]


@pytest.mark.parametrize(
    ("sort", "order", "expected"),
    [
        ("project", "asc", ["a", "b", "c"]),
        ("project", "desc", ["c", "b", "a"]),
        ("used", "asc", ["a", "c", "b"]),
        ("used", "desc", ["b", "c", "a"]),
    ],
)
async def test_정렬_기준과_방향을_따른다(
    client: AsyncClient,
    factory: Factory,
    sort: str,
    order: str,
    expected: list[str],
) -> None:
    await project_with_usage(factory, "a", "1")
    await project_with_usage(factory, "b", "9")
    await project_with_usage(factory, "c", "5")
    params = {**OCTOBER, "sort": sort, "order": order}

    body = (await client.get(PROJECTS, params=params)).json()

    assert names(body) == expected


async def test_미리보기는_사용률_상위_5개만_돌려주고_total은_전체_수이다(
    client: AsyncClient, factory: Factory
) -> None:
    for number in range(1, 7):
        await project_with_usage(factory, f"p{number}", str(number * 10), "100")
    # 사용액은 가장 크지만 사용률은 가장 낮다. 미리보기에 들어오면 안 된다.
    await project_with_usage(factory, "큰 예산", "500", "100000")
    params = {**OCTOBER, "preview": "true", "sort": "project", "order": "asc"}

    body = (await client.get(PROJECTS, params=params)).json()

    assert names(body) == ["p2", "p3", "p4", "p5", "p6"]
    assert body["total"] == 7


async def test_예산이_없는_프로젝트만_있으면_미리보기는_사용액_상위_5개이다(
    client: AsyncClient, factory: Factory
) -> None:
    for number in range(1, 8):
        await project_with_usage(factory, f"p{number}", str(number))
    params = {**OCTOBER, "preview": "true", "sort": "project", "order": "asc"}

    body = (await client.get(PROJECTS, params=params)).json()

    assert names(body) == ["p3", "p4", "p5", "p6", "p7"]


async def test_페이지를_나누어_돌려준다(client: AsyncClient, factory: Factory) -> None:
    for number in range(1, 6):
        await project_with_usage(factory, f"p{number}", str(number))
    params = {**OCTOBER, "page": "2", "page_size": "2"}

    body = (await client.get(PROJECTS, params=params)).json()

    assert names(body) == ["p3", "p2"]
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2


@pytest.mark.parametrize(
    ("page_size", "expected_status"),
    [
        (100, status.HTTP_200_OK),
        (101, status.HTTP_422_UNPROCESSABLE_CONTENT),
        (1, status.HTTP_200_OK),
        (0, status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
    ids=["100개", "101개", "1개", "0개"],
)
async def test_페이지_크기는_1에서_100까지이다(
    client: AsyncClient, factory: Factory, page_size: int, expected_status: int
) -> None:
    params = {**OCTOBER, "page_size": str(page_size)}

    response = await client.get(PROJECTS, params=params)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"month": "2026-13"},
        {"month": "2026-10-01"},
        {"month": "2026-10", "sort": "unknown"},
        {"month": "2026-10", "order": "up"},
        {"month": "2026-10", "page": "0"},
        {"month": "2026-10", "unknown_param": "1"},
    ],
    ids=[
        "월 없음",
        "없는 월",
        "일까지 있음",
        "허용하지 않는 정렬",
        "허용하지 않는 방향",
        "0쪽",
        "모르는 조건",
    ],
)
async def test_잘못된_조건은_422이다(
    client: AsyncClient, factory: Factory, params: dict[str, str]
) -> None:
    response = await client.get(PROJECTS, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_프로젝트를_고르면_그_프로젝트_한_행만_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    await project_with_usage(factory, "다른", "5", budget="100")
    target = await project_with_usage(factory, "대상", "10", budget="100")
    params = {**OCTOBER, "project_id": target}

    body = (await client.get(PROJECTS, params=params)).json()

    assert names(body) == ["대상"]
    assert body["total"] == 1


async def test_모델을_고르면_그_모델의_호출만_사용액이고_구독료는_뺀다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project(name="프로젝트")
    project_id = project["project_id"]
    model = await factory.model()
    other = await factory.model()
    await factory.budget(project_id=project_id, monthly_amount_usd=Decimal(100))
    await internal_call(
        factory, project_id=project_id, model_id=model["model_id"], cost_usd=Decimal(10)
    )
    await internal_call(
        factory, project_id=project_id, model_id=other["model_id"], cost_usd=Decimal(30)
    )
    await factory.subscription_cost(
        applied_month=date(2026, 10, 1), amount=Decimal(5), project_id=project_id
    )
    params = {**OCTOBER, "model_id": model["model_id"]}

    unfiltered = (await client.get(PROJECTS, params=OCTOBER)).json()["items"][0]
    filtered = (await client.get(PROJECTS, params=params)).json()["items"][0]

    assert Decimal(unfiltered["used_usd"]) == Decimal(45)
    assert Decimal(filtered["used_usd"]) == Decimal(10)


@pytest.mark.parametrize(
    "params",
    [
        {"project_id": "0"},
        {"project_id": "abc"},
        {"model_id": "-1"},
    ],
    ids=["프로젝트 ID 0", "프로젝트 ID가 숫자 아님", "모델 ID 음수"],
)
async def test_잘못된_프로젝트_모델_번호는_422이다(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(PROJECTS, params={**OCTOBER, **params})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

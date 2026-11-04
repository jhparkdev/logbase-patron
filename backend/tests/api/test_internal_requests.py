"""GET /api/usage/internal/requests·options 테스트. 내부 AI 예산 관리(P-02)의 호출 이력을 확인한다."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient

from tests.db_helpers import Factory
from tests.internal_budget_helpers import UNKNOWN_COST, internal_call

# 로그인한 사용자만 부를 수 있는 API다. 로그인 경계는 tests/test_main.py 에서 확인한다
pytestmark = pytest.mark.usefixtures("signed_in")

REQUESTS = "/api/usage/internal/requests"
OPTIONS = "/api/usage/internal/options"
OCTOBER = {"start_date": "2026-10-01", "end_date": "2026-10-31"}


async def test_호출_이력은_행과_total과_페이지_정보를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    task = await factory.task(task_type="IMAGE_ANALYSIS")
    created = await internal_call(
        factory,
        project_id=project["project_id"],
        task_id=task["task_id"],
        usage_origin="SIMULATION",
        input_tokens=10,
        output_tokens=5,
        status="SUCCESS",
        cost_usd=Decimal("0.02"),
    )

    response = await client.get(REQUESTS, params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert (body["total"], body["page"], body["page_size"]) == (1, 1, 10)
    row = body["items"][0]
    assert row["request_id"] == str(created["request_id"])
    assert row["usage_origin"] == "SIMULATION"
    assert row["project_name"] == "알파"
    assert row["task_type_label"] == "이미지 분석"
    assert row["tokens"] == 15
    assert Decimal(row["cost_usd"]) == Decimal("0.02")
    assert row["cost_status"] == "CONFIRMED"
    assert row["status"] == "SUCCESS"
    assert row["error_type"] is None
    assert row["requested_at"]


async def test_비용을_모르는_호출은_비용이_null이다(
    client: AsyncClient, factory: Factory
) -> None:
    await internal_call(factory, **UNKNOWN_COST)

    row = (await client.get(REQUESTS, params=OCTOBER)).json()["items"][0]

    assert row["cost_usd"] is None
    assert row["cost_status"] == "UNKNOWN"


async def test_비용은_문자열이고_작은_값도_지수_표기가_아니다(
    client: AsyncClient, factory: Factory
) -> None:
    await internal_call(factory, cost_usd=Decimal("0.00000003"))

    row = (await client.get(REQUESTS, params=OCTOBER)).json()["items"][0]

    assert isinstance(row["cost_usd"], str)
    assert "e" not in row["cost_usd"].lower()
    assert Decimal(row["cost_usd"]) == Decimal("0.00000003")


async def test_고객_호출은_나오지_않는다(client: AsyncClient, factory: Factory) -> None:
    await internal_call(factory, usage_origin="CUSTOMER_SERVICE")

    body = (await client.get(REQUESTS, params=OCTOBER)).json()

    assert body["items"] == []
    assert body["total"] == 0


async def test_정렬과_미리보기와_페이지_조건을_받는다(
    client: AsyncClient, factory: Factory
) -> None:
    for cost in (3, 1, 2):
        await internal_call(factory, cost_usd=Decimal(cost))

    ordered = await client.get(
        REQUESTS, params={**OCTOBER, "sort": "cost", "order": "asc"}
    )
    previewed = await client.get(REQUESTS, params={**OCTOBER, "preview": "true"})
    paged = await client.get(REQUESTS, params={**OCTOBER, "page": 2, "page_size": 2})

    costs = [Decimal(row["cost_usd"]) for row in ordered.json()["items"]]
    assert costs == [Decimal(1), Decimal(2), Decimal(3)]
    assert previewed.json()["total"] == 3
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] == 3


async def test_호출_이력은_호출_출처로_정렬할_수_있다(
    client: AsyncClient, factory: Factory
) -> None:
    for origin in ("SYSTEM_TEST", "INTERNAL_DEVELOPMENT"):
        await internal_call(factory, usage_origin=origin)

    response = await client.get(
        REQUESTS, params={**OCTOBER, "sort": "origin", "order": "asc"}
    )

    origins = [row["usage_origin"] for row in response.json()["items"]]
    assert origins == ["INTERNAL_DEVELOPMENT", "SYSTEM_TEST"]


async def test_기간을_보내지_않으면_최근_30일을_조회한다(
    client: AsyncClient, factory: Factory
) -> None:
    response = await client.get(REQUESTS)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2026-10-01"},
        {"start_date": "2026-10-31", "end_date": "2026-10-01"},
        {"start_date": "2025-12-30", "end_date": "2026-12-31"},
    ],
    ids=["시작일만 있음", "시작일이 종료일보다 늦음", "367일"],
)
async def test_잘못된_기간은_INVALID_PERIOD로_거절한다(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(REQUESTS, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "INVALID_PERIOD"


@pytest.mark.parametrize(
    "params",
    [
        {"unknown_param": "1"},
        {"sort": "unknown"},
        {"sort": "customer"},
        {"order": "up"},
        {"page": "0"},
        {"page_size": "0"},
        {"page_size": "101"},
        {"project_id": "0"},
        {"service_id": "abc"},
        {"model_id": "-1"},
    ],
    ids=[
        "모르는 조건",
        "허용하지 않는 정렬",
        "고객 정렬은 없음",
        "허용하지 않는 방향",
        "0쪽",
        "0개",
        "101개",
        "프로젝트 ID 0",
        "서비스 ID가 숫자 아님",
        "모델 ID 음수",
    ],
)
async def test_허용하지_않는_조건은_422이다(
    client: AsyncClient, params: dict[str, Any]
) -> None:
    response = await client.get(REQUESTS, params={**OCTOBER, **params})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_선택_목록은_프로젝트_서비스_모델을_id와_이름으로_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    service = await factory.service(name="시뮬레이터")
    model = await factory.model(display_name="모델 가")
    await internal_call(
        factory, service_id=service["service_id"], model_id=model["model_id"]
    )

    response = await client.get(OPTIONS)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert {"id": project["project_id"], "name": "알파"} in body["projects"]
    assert body["services"] == [{"id": service["service_id"], "name": "시뮬레이터"}]
    assert body["models"] == [{"id": model["model_id"], "name": "모델 가"}]

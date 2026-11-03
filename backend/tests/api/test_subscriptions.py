"""GET·PATCH /api/subscriptions 테스트. 월 구독료 목록, 프로젝트 선택 목록, 수정을 확인한다."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy import select

from app.models import ChangeLog
from app.schemas.models import MAX_MODEL_ID
from tests.db_helpers import Factory

BASE = "/api/subscriptions"
OCTOBER = {"start_date": "2026-10-01", "end_date": "2026-10-31"}
OCT = date(2026, 10, 1)


# ---------------------------------------------------------------
# 목록
# ---------------------------------------------------------------
async def test_목록은_구독료와_프로젝트_이름을_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    project = await factory.project(name="알파")
    await factory.subscription_cost(
        applied_month=OCT,
        subscription_reference="CommandCode_team1",
        tool_name="Command Code",
        subscription_type="TEAM",
        amount=Decimal("20.5"),
        project_id=project["project_id"],
        note="10월분",
    )

    response = await client.get(BASE, params=OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["subscription_reference"] == "CommandCode_team1"
    assert item["tool_name"] == "Command Code"
    assert item["subscription_type"] == "TEAM"
    assert item["applied_month"] == "2026-10"
    assert Decimal(item["amount_usd"]) == Decimal("20.5")
    assert item["project_id"] == project["project_id"]
    assert item["project_name"] == "알파"
    assert item["status"] == "ACTIVE"
    assert item["note"] == "10월분"


async def test_프로젝트가_없는_구독료는_미배분으로_null이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.subscription_cost(applied_month=OCT)

    item = (await client.get(BASE, params=OCTOBER)).json()["items"][0]

    assert item["project_id"] is None
    assert item["project_name"] is None


async def test_금액은_문자열이고_작은_값도_지수_표기가_아니다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.subscription_cost(applied_month=OCT, amount=Decimal("0.0001"))

    item = (await client.get(BASE, params=OCTOBER)).json()["items"][0]

    assert isinstance(item["amount_usd"], str)
    assert "e" not in item["amount_usd"].lower()
    assert Decimal(item["amount_usd"]) == Decimal("0.0001")


async def test_다른_달의_구독료는_목록에_없다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.subscription_cost(applied_month=date(2026, 9, 1))

    response = await client.get(BASE, params=OCTOBER)

    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 10}


async def test_조회_기간이_걸치는_모든_달의_구독료를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    for month in (date(2026, 9, 1), OCT, date(2026, 11, 1)):
        await factory.subscription_cost(applied_month=month)
    params = {"start_date": "2026-09-30", "end_date": "2026-10-31"}

    body = (await client.get(BASE, params=params)).json()

    months = sorted(item["applied_month"] for item in body["items"])
    assert months == ["2026-09", "2026-10"]
    assert body["total"] == 2


async def test_기간을_보내지_않으면_최근_30일이_걸치는_달을_조회한다(
    client: AsyncClient, factory: Factory
) -> None:
    # 고정 시각은 2026-10-01(UTC)이라 최근 30일은 2026-09-02부터 2026-10-01(KST)까지다.
    await factory.subscription_cost(applied_month=date(2026, 9, 1))
    await factory.subscription_cost(applied_month=OCT)
    await factory.subscription_cost(applied_month=date(2026, 8, 1))

    body = (await client.get(BASE)).json()

    months = sorted(item["applied_month"] for item in body["items"])
    assert months == ["2026-09", "2026-10"]


async def test_정렬_기준과_방향을_따라_순서를_바꾼다(
    client: AsyncClient, factory: Factory
) -> None:
    for tool, amount in (("나", "20"), ("가", "30"), ("다", "10")):
        await factory.subscription_cost(
            applied_month=OCT, tool_name=tool, amount=Decimal(amount)
        )
    params = {**OCTOBER, "sort": "amount", "order": "asc"}

    body = (await client.get(BASE, params=params)).json()

    assert [item["tool_name"] for item in body["items"]] == ["다", "나", "가"]


async def test_기본_정렬은_적용_월_최신순이다(
    client: AsyncClient, factory: Factory
) -> None:
    for month, tool in ((date(2026, 9, 1), "구월"), (OCT, "시월")):
        await factory.subscription_cost(applied_month=month, tool_name=tool)
    params = {"start_date": "2026-09-01", "end_date": "2026-10-31"}

    body = (await client.get(BASE, params=params)).json()

    assert [item["tool_name"] for item in body["items"]] == ["시월", "구월"]


async def test_미리보기는_최근_5건을_고른_뒤_그_안에서_정렬하고_total은_전체_수이다(
    client: AsyncClient, factory: Factory
) -> None:
    for month_number, tool in enumerate("abcdefg", start=4):
        await factory.subscription_cost(
            applied_month=date(2026, month_number, 1), tool_name=tool
        )
    params = {
        "start_date": "2026-04-01",
        "end_date": "2026-10-31",
        "preview": "true",
        "sort": "tool",
        "order": "asc",
    }

    body = (await client.get(BASE, params=params)).json()

    assert [item["tool_name"] for item in body["items"]] == ["c", "d", "e", "f", "g"]
    assert body["total"] == 7


async def test_페이지를_나누어_돌려준다(client: AsyncClient, factory: Factory) -> None:
    for number in range(1, 6):
        await factory.subscription_cost(applied_month=OCT, tool_name=f"도구 {number}")
    params = {**OCTOBER, "sort": "tool", "order": "asc", "page": 2, "page_size": 2}

    body = (await client.get(BASE, params=params)).json()

    assert [item["tool_name"] for item in body["items"]] == ["도구 3", "도구 4"]
    assert (body["total"], body["page"], body["page_size"]) == (5, 2, 2)


async def test_같은_기간의_목록_금액_합계가_요약의_구독료와_같다(
    client: AsyncClient, factory: Factory
) -> None:
    amounts = {date(2026, 9, 1): "10", OCT: "20", date(2026, 11, 1): "40"}
    for month, amount in amounts.items():
        await factory.subscription_cost(applied_month=month, amount=Decimal(amount))
    period = {"start_date": "2026-09-15", "end_date": "2026-10-10"}

    listed = (await client.get(BASE, params={**period, "page_size": 100})).json()
    summary = (await client.get("/api/usage/internal/summary", params=period)).json()

    total = sum(Decimal(item["amount_usd"]) for item in listed["items"])
    assert total == Decimal(30)
    assert Decimal(summary["subscription_usd"]) == total


async def test_프로젝트를_고르면_그_프로젝트에_배분한_구독료만_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    mine = await factory.project(name="내 프로젝트")
    await factory.subscription_cost(
        applied_month=OCT, tool_name="내 것", project_id=mine["project_id"]
    )
    await factory.subscription_cost(applied_month=OCT, tool_name="미배분")
    params = {**OCTOBER, "project_id": mine["project_id"]}

    body = (await client.get(BASE, params=params)).json()

    assert [item["tool_name"] for item in body["items"]] == ["내 것"]
    assert body["total"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {"month": "2026-10"},
        {"unknown_param": "1"},
        {"sort": "unknown"},
        {"sort": "note"},
        {"order": "up"},
        {"page": "0"},
        {"page_size": "0"},
        {"page_size": "101"},
        {"project_id": "0"},
        {"model_id": "1"},
    ],
    ids=[
        "예전 month 조건",
        "모르는 조건",
        "허용하지 않는 정렬",
        "메모 정렬은 없음",
        "허용하지 않는 방향",
        "0쪽",
        "0개",
        "101개",
        "프로젝트 ID 0",
        "모델 조건은 없음",
    ],
)
async def test_잘못된_목록_조건은_422이다(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(BASE, params={**OCTOBER, **params})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


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
    response = await client.get(BASE, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "INVALID_PERIOD"


# ---------------------------------------------------------------
# 프로젝트 선택 목록
# ---------------------------------------------------------------
async def test_선택_목록은_사용_중인_프로젝트를_이름순으로_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    second = await factory.project(name="나")
    first = await factory.project(name="가")
    await factory.project(name="중단됨", is_active=False)

    response = await client.get(f"{BASE}/options")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "projects": [
            {"project_id": first["project_id"], "name": "가"},
            {"project_id": second["project_id"], "name": "나"},
        ]
    }


# ---------------------------------------------------------------
# 등록
# ---------------------------------------------------------------
def create_body(**values: Any) -> dict[str, Any]:
    return {
        "subscription_reference": "CommandCode_team1",
        "tool_name": "Command Code",
        "applied_month": "2026-10",
        "amount_usd": "20.5",
        **values,
    }


def without(name: str) -> dict[str, Any]:
    return {key: value for key, value in create_body().items() if key != name}


async def test_등록하면_201과_만들어진_행을_돌려주고_목록에도_나온다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project(name="알파")
    body = create_body(
        subscription_type="Team", project_id=project["project_id"], note="10월분"
    )

    response = await client.post(BASE, json=body)
    listed = (await client.get(BASE, params=OCTOBER)).json()["items"]

    assert response.status_code == status.HTTP_201_CREATED
    item = response.json()
    assert item["subscription_reference"] == "CommandCode_team1"
    assert item["tool_name"] == "Command Code"
    assert item["subscription_type"] == "Team"
    assert item["applied_month"] == "2026-10"
    assert Decimal(item["amount_usd"]) == Decimal("20.5")
    assert item["project_id"] == project["project_id"]
    assert item["project_name"] == "알파"
    assert item["status"] == "ACTIVE"
    assert item["note"] == "10월분"
    assert len(listed) == 1
    assert listed[0]["subscription_id"] == item["subscription_id"]
    assert Decimal(listed[0]["amount_usd"]) == Decimal("20.5")


async def test_프로젝트와_종류와_메모는_보내지_않아도_된다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.post(BASE, json=create_body())

    assert response.status_code == status.HTTP_201_CREATED
    item = response.json()
    assert item["project_id"] is None
    assert item["subscription_type"] is None
    assert item["note"] is None


async def test_앞뒤_공백은_지우고_저장한다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    body = create_body(subscription_reference="  CommandCode_team1 ", tool_name=" CC ")

    item = (await client.post(BASE, json=body)).json()

    assert item["subscription_reference"] == "CommandCode_team1"
    assert item["tool_name"] == "CC"


async def test_등록은_첫_사용자_계정과_이력을_남긴다(
    client: AsyncClient, factory: Factory
) -> None:
    # 로그인 검사를 뒤로 미룬 팀 결정에 따라 시뮬레이터와 같은 임시 실행자를 쓴다
    user = await factory.user()

    created = (await client.post(BASE, json=create_body())).json()

    log = await factory.session.scalar(
        select(ChangeLog).where(
            ChangeLog.entity_type == "subscription_costs",
            ChangeLog.entity_id == str(created["subscription_id"]),
        )
    )
    assert log is not None
    assert log.action == "CREATE"
    assert log.changed_by == user["user_id"]


async def test_같은_식별값과_같은_달이면_409와_문구를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    await client.post(BASE, json=create_body())

    response = await client.post(BASE, json=create_body(amount_usd="99"))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "SUBSCRIPTION_DUPLICATE"
    assert response.json()["message"]
    items = (await client.get(BASE, params=OCTOBER)).json()["items"]
    assert [Decimal(item["amount_usd"]) for item in items] == [Decimal("20.5")]


async def test_같은_식별값이어도_다른_달이면_등록된다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    await client.post(BASE, json=create_body(applied_month="2026-09"))

    response = await client.post(BASE, json=create_body(applied_month="2026-10"))

    assert response.status_code == status.HTTP_201_CREATED


async def test_없는_프로젝트로_등록하면_422이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.post(BASE, json=create_body(project_id=987654))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert (await client.get(BASE, params=OCTOBER)).json()["items"] == []


async def test_금액_0은_등록할_수_있다(client: AsyncClient, factory: Factory) -> None:
    await factory.user()

    response = await client.post(BASE, json=create_body(amount_usd="0"))

    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.json()["amount_usd"]) == 0


async def test_상태를_보내면_그_상태로_등록한다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.post(BASE, json=create_body(status="CANCELLED"))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["status"] == "CANCELLED"
    listed = (await client.get(BASE, params=OCTOBER)).json()["items"]
    assert [item["status"] for item in listed] == ["CANCELLED"]


async def test_상태를_진행_중으로_보내도_등록된다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.post(BASE, json=create_body(status="ACTIVE"))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["status"] == "ACTIVE"


async def test_OpenAPI에서_등록_본문의_상태는_필수가_아니다(app: FastAPI) -> None:
    schema = app.openapi()["components"]["schemas"]["SubscriptionCreate"]

    assert "status" not in schema.get("required", [])
    # default가 있으면 생성된 프론트엔드 타입에서 필수 항목이 된다
    assert "default" not in schema["properties"]["status"]


@pytest.mark.parametrize(
    "body",
    [
        without("subscription_reference"),
        without("tool_name"),
        without("applied_month"),
        without("amount_usd"),
        create_body(subscription_reference=""),
        create_body(subscription_reference="   "),
        create_body(subscription_reference="x" * 101),
        create_body(tool_name=""),
        create_body(tool_name="x" * 101),
        create_body(subscription_type=""),
        create_body(applied_month="2026-10-01"),
        create_body(applied_month="2026-13"),
        create_body(amount_usd="-1"),
        create_body(amount_usd=20.5),
        create_body(amount_usd="NaN"),
        create_body(amount_usd="10.12345"),
        create_body(amount_usd="10000000000"),
        create_body(amount_usd=None),
        create_body(project_id=0),
        create_body(note="x" * 501),
        create_body(status="UNKNOWN"),
        create_body(status="cancelled"),
        create_body(status=None),
    ],
    ids=[
        "식별값 없음",
        "도구 이름 없음",
        "적용 월 없음",
        "금액 없음",
        "빈 식별값",
        "공백뿐인 식별값",
        "식별값이 너무 김",
        "빈 도구 이름",
        "도구 이름이 너무 김",
        "빈 종류",
        "일까지 있는 월",
        "없는 월",
        "음수 금액",
        "숫자 금액",
        "NaN",
        "소수 5자리",
        "금액 한도",
        "금액 null",
        "프로젝트 ID 0",
        "메모가 너무 김",
        "모르는 상태",
        "소문자 상태",
        "상태 null",
    ],
)
async def test_잘못된_등록_본문은_422이다(
    client: AsyncClient, factory: Factory, body: dict[str, Any]
) -> None:
    await factory.user()

    response = await client.post(BASE, json=body)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_허용하지_않는_Origin의_등록은_거절한다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.post(
        BASE, json=create_body(), headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"


# ---------------------------------------------------------------
# 단건 조회
# ---------------------------------------------------------------
async def test_번호로_한_건을_돌려준다(client: AsyncClient, factory: Factory) -> None:
    project = await factory.project(name="알파")
    created = await factory.subscription_cost(
        applied_month=date(2025, 1, 1),
        tool_name="도구",
        project_id=project["project_id"],
    )

    response = await client.get(f"{BASE}/{created['subscription_id']}")

    assert response.status_code == status.HTTP_200_OK
    item = response.json()
    assert item["subscription_id"] == created["subscription_id"]
    assert (item["tool_name"], item["project_name"]) == ("도구", "알파")
    assert item["applied_month"] == "2025-01"


async def test_목록에_없는_기간의_구독료도_번호로_조회된다(
    client: AsyncClient, factory: Factory
) -> None:
    created = await factory.subscription_cost(applied_month=date(2025, 1, 1))

    listed = (await client.get(BASE)).json()["items"]
    response = await client.get(f"{BASE}/{created['subscription_id']}")

    assert listed == []
    assert response.status_code == status.HTTP_200_OK


async def test_없는_번호의_조회는_404이다(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/987654")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize("subscription_id", ["0", "-1", "abc", str(MAX_MODEL_ID + 1)])
async def test_잘못된_번호의_조회는_422이다(
    client: AsyncClient, subscription_id: str
) -> None:
    response = await client.get(f"{BASE}/{subscription_id}")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_options는_번호로_해석되지_않는다(client: AsyncClient) -> None:
    response = await client.get(f"{BASE}/options")

    assert response.status_code == status.HTTP_200_OK
    assert "projects" in response.json()


# ---------------------------------------------------------------
# 수정
# ---------------------------------------------------------------
async def test_수정하면_바뀐_행을_돌려주고_목록에도_반영된다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project(name="알파")
    created = await factory.subscription_cost(applied_month=OCT, amount=Decimal(10))
    path = f"{BASE}/{created['subscription_id']}"
    body = {
        "amount_usd": "12.5",
        "project_id": project["project_id"],
        "status": "CANCELLED",
        "note": "해지함",
    }

    response = await client.patch(path, json=body)
    listed = (await client.get(BASE, params=OCTOBER)).json()["items"][0]

    assert response.status_code == status.HTTP_200_OK
    for item in (response.json(), listed):
        assert item["subscription_id"] == created["subscription_id"]
        assert Decimal(item["amount_usd"]) == Decimal("12.5")
        assert item["project_name"] == "알파"
        assert item["status"] == "CANCELLED"
        assert item["note"] == "해지함"


async def test_보낸_항목만_바뀌고_나머지는_그대로이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project()
    created = await factory.subscription_cost(
        amount=Decimal(10), project_id=project["project_id"], note="그대로"
    )

    response = await client.patch(
        f"{BASE}/{created['subscription_id']}", json={"amount_usd": "11"}
    )

    item = response.json()
    assert Decimal(item["amount_usd"]) == Decimal(11)
    assert item["project_id"] == project["project_id"]
    assert item["note"] == "그대로"
    assert item["status"] == "ACTIVE"


async def test_project_id를_null로_보내면_미배분이_된다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    project = await factory.project()
    created = await factory.subscription_cost(project_id=project["project_id"])

    response = await client.patch(
        f"{BASE}/{created['subscription_id']}", json={"project_id": None}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["project_id"] is None
    assert response.json()["project_name"] is None


async def test_수정은_첫_사용자_계정과_이력을_남긴다(
    client: AsyncClient, factory: Factory
) -> None:
    # 로그인 검사를 뒤로 미룬 팀 결정에 따라 시뮬레이터와 같은 임시 실행자를 쓴다
    user = await factory.user()
    created = await factory.subscription_cost(amount=Decimal(10))

    await client.patch(
        f"{BASE}/{created['subscription_id']}", json={"amount_usd": "11"}
    )

    log = await factory.session.scalar(
        select(ChangeLog).where(
            ChangeLog.entity_type == "subscription_costs",
            ChangeLog.entity_id == str(created["subscription_id"]),
        )
    )
    assert log is not None
    assert log.changed_by == user["user_id"]


async def test_없는_구독료의_수정은_404이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()

    response = await client.patch(f"{BASE}/987654", json={"note": "x"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["code"] == "NOT_FOUND"


async def test_없는_프로젝트로_바꾸면_422이고_아무것도_바뀌지_않는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    created = await factory.subscription_cost(applied_month=OCT, amount=Decimal(10))

    response = await client.patch(
        f"{BASE}/{created['subscription_id']}",
        json={"amount_usd": "99", "project_id": 987654},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"
    item = (await client.get(BASE, params=OCTOBER)).json()["items"][0]
    assert Decimal(item["amount_usd"]) == Decimal(10)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"amount_usd": "-1"},
        {"amount_usd": 10.5},
        {"amount_usd": "NaN"},
        {"amount_usd": "10.12345"},
        {"amount_usd": "10000000000"},
        {"amount_usd": None},
        {"status": "UNKNOWN"},
        {"status": None},
        {"project_id": 0},
        {"note": "x" * 501},
        {"tool_name": "바꿀 수 없음"},
    ],
    ids=[
        "빈 본문",
        "음수 금액",
        "숫자 금액",
        "NaN",
        "소수 5자리",
        "금액 한도",
        "금액 null",
        "없는 상태",
        "상태 null",
        "프로젝트 ID 0",
        "메모가 너무 김",
        "수정할 수 없는 필드",
    ],
)
async def test_잘못된_수정_본문은_422이다(
    client: AsyncClient, factory: Factory, body: dict[str, Any]
) -> None:
    await factory.user()
    created = await factory.subscription_cost()

    response = await client.patch(f"{BASE}/{created['subscription_id']}", json=body)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_금액_0과_빈_메모는_허용한다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    created = await factory.subscription_cost(note="지울 메모")

    response = await client.patch(
        f"{BASE}/{created['subscription_id']}", json={"amount_usd": "0", "note": None}
    )

    assert response.status_code == status.HTTP_200_OK
    assert Decimal(response.json()["amount_usd"]) == 0
    assert response.json()["note"] is None


async def test_허용하지_않는_Origin의_수정은_거절한다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.user()
    created = await factory.subscription_cost()

    response = await client.patch(
        f"{BASE}/{created['subscription_id']}",
        json={"note": "x"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"

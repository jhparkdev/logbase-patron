"""app/api/models.py 테스트. 모델 목록(GET /api/models)의 필터·정렬·페이지·응답 계약을 확인한다."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient

from app.schemas.models import (
    DEFAULT_PAGE_SIZE,
    MAX_FILTER_LENGTH,
    MAX_MODEL_ID,
    MAX_PAGE,
    MAX_PAGE_SIZE,
)
from tests.db_helpers import T0, Factory

MODELS = "/api/models"


def names(body: dict[str, Any]) -> list[str]:
    return [item["display_name"] for item in body["items"]]


# ---------------------------------------------------------------
# 응답 모양
# ---------------------------------------------------------------
async def test_등록한_모델이_없으면_빈_목록이다(client: AsyncClient) -> None:
    response = await client.get(MODELS)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": DEFAULT_PAGE_SIZE,
        "total": 0,
    }


async def test_모델_한_건의_필드를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(
        openrouter_model_id="vendor/a",
        provider="vendor",
        display_name="모델 A",
        purpose="요약",
        input_modalities=["text", "image"],
        output_modalities=["text"],
        supported_parameters=["response_format"],
        context_length=1000,
    )
    await factory.model_price(
        model_id=model["model_id"],
        input_price_per_token=Decimal("0.000002"),
        output_price_per_token=Decimal("0.00001"),
        cache_read_price_per_token=Decimal("0.0000002"),
    )

    body = (await client.get(MODELS)).json()

    assert body["total"] == 1
    item = body["items"][0]
    assert item["model_id"] == model["model_id"]
    assert item["openrouter_model_id"] == "vendor/a"
    assert item["provider"] == "vendor"
    assert item["display_name"] == "모델 A"
    assert item["purpose"] == "요약"
    assert item["status"] == "TESTING"
    assert item["input_modalities"] == ["text", "image"]
    assert item["output_modalities"] == ["text"]
    assert item["supports_json_schema"] is True
    assert item["context_length"] == 1000
    assert item["last_test_status"] is None
    assert item["last_test_at"] is None


async def test_금액은_문자열로_돌려준다(client: AsyncClient, factory: Factory) -> None:
    model = await factory.model()
    await factory.model_price(
        model_id=model["model_id"],
        input_price_per_token=Decimal("0.000002"),
        output_price_per_token=Decimal("0.00001"),
        cache_read_price_per_token=Decimal("0.0000002"),
    )

    price = (await client.get(MODELS)).json()["items"][0]["current_price"]

    assert isinstance(price["input_price_per_token"], str)
    assert Decimal(price["input_price_per_token"]) == Decimal("0.000002")
    assert Decimal(price["output_price_per_token"]) == Decimal("0.00001")
    assert Decimal(price["cache_read_price_per_token"]) == Decimal("0.0000002")
    assert price["cache_write_price_per_token"] is None
    assert price["price_status"] == "KNOWN"


async def test_response_format이_없으면_JSON_Schema를_지원하지_않는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(supported_parameters=["temperature"])

    item = (await client.get(MODELS)).json()["items"][0]

    assert item["supports_json_schema"] is False


async def test_가격이_없는_모델은_current_price가_null이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model()

    item = (await client.get(MODELS)).json()["items"][0]

    assert item["current_price"] is None


async def test_현재_가격은_종료되지_않은_대표가격이다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()
    model_id = model["model_id"]
    day = timedelta(days=1)
    # 종료된 옛 가격, 현재 대표가격, 특정 업체 가격이 함께 있어도 현재 대표가격만 보인다.
    await factory.model_price(
        model_id=model_id,
        input_price_per_token=Decimal("0.1"),
        effective_to=T0 + day,
    )
    await factory.model_price(
        model_id=model_id,
        input_price_per_token=Decimal("0.2"),
        effective_from=T0 + day,
    )
    await factory.model_price(
        model_id=model_id,
        execution_provider="SomeProvider",
        input_price_per_token=Decimal("0.3"),
        effective_from=T0 + day,
    )

    body = (await client.get(MODELS)).json()

    assert body["total"] == 1
    price = body["items"][0]["current_price"]
    assert Decimal(price["input_price_per_token"]) == Decimal("0.2")
    assert price["execution_provider"] is None


# ---------------------------------------------------------------
# 검색 조건
# ---------------------------------------------------------------
async def test_표시_이름은_부분_일치이고_대소문자를_구분하지_않는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="GPT-4o Mini")
    await factory.model(display_name="Claude Sonnet")

    body = (await client.get(MODELS, params={"name": "gpt"})).json()

    assert names(body) == ["GPT-4o Mini"]


async def test_모델_ID와_제공사로도_찾는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(
        display_name="A", openrouter_model_id="openai/gpt-4o", provider="openai"
    )
    await factory.model(
        display_name="B", openrouter_model_id="mistralai/nemo", provider="mistralai"
    )

    by_id = (await client.get(MODELS, params={"model_id": "nemo"})).json()
    by_provider = (await client.get(MODELS, params={"provider": "open"})).json()

    assert names(by_id) == ["B"]
    assert names(by_provider) == ["A"]


async def test_q는_표시_이름이나_모델_ID_중_하나에만_맞아도_찾는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="GPT Mini", openrouter_model_id="openai/mini")
    await factory.model(display_name="Other", openrouter_model_id="acme/unique-id")
    await factory.model(display_name="Nothing", openrouter_model_id="vendor/none")

    by_name = (await client.get(MODELS, params={"q": "gpt"})).json()
    by_id = (await client.get(MODELS, params={"q": "unique"})).json()

    assert names(by_name) == ["GPT Mini"]
    assert names(by_id) == ["Other"]


async def test_q는_대소문자를_구분하지_않는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="Target", openrouter_model_id="acme/Unique-ID")

    body = (await client.get(MODELS, params={"q": "UNIQUE"})).json()

    assert names(body) == ["Target"]


async def test_q는_다른_조건과_함께_모두_맞아야_찾는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="gpt active", status="ACTIVE")
    await factory.model(display_name="gpt testing", status="TESTING")
    await factory.model(display_name="other active", status="ACTIVE")

    params = {"q": "gpt", "status": "ACTIVE"}
    body = (await client.get(MODELS, params=params)).json()

    assert names(body) == ["gpt active"]


async def test_q의_퍼센트와_밑줄도_글자_그대로_찾는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="100% 모델", openrouter_model_id="acme/a")
    await factory.model(display_name="밑줄", openrouter_model_id="acme/a_b")
    await factory.model(display_name="다른", openrouter_model_id="acme/axb")

    percent = (await client.get(MODELS, params={"q": "%"})).json()
    underscore = (await client.get(MODELS, params={"q": "a_b"})).json()

    assert names(percent) == ["100% 모델"]
    assert names(underscore) == ["밑줄"]


@pytest.mark.parametrize(
    ("q", "expected_status"),
    [
        ("", status.HTTP_422_UNPROCESSABLE_CONTENT),
        ("x" * MAX_FILTER_LENGTH, status.HTTP_200_OK),
        ("x" * (MAX_FILTER_LENGTH + 1), status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
)
async def test_q의_글자수_경계(
    client: AsyncClient, q: str, expected_status: int
) -> None:
    response = await client.get(MODELS, params={"q": q})

    assert response.status_code == expected_status


async def test_검색어의_퍼센트와_밑줄은_글자_그대로_찾는다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="100% 모델")
    await factory.model(display_name="a_b")
    await factory.model(display_name="axb")
    await factory.model(display_name="그 밖의 모델")

    percent = (await client.get(MODELS, params={"name": "%"})).json()
    underscore = (await client.get(MODELS, params={"name": "a_b"})).json()

    assert names(percent) == ["100% 모델"]
    assert names(underscore) == ["a_b"]


async def test_상태는_여러_개를_함께_고를_수_있다(
    client: AsyncClient, factory: Factory
) -> None:
    # 정렬 순서를 확인하는 테스트는 영문 이름을 쓴다. 한글 순서는 DB 정렬 규칙에 따라 달라진다.
    await factory.model(display_name="testing", status="TESTING")
    await factory.model(display_name="active", status="ACTIVE")
    await factory.model(display_name="inactive", status="INACTIVE")

    params = {"status": ["ACTIVE", "INACTIVE"], "sort": "display_name", "order": "asc"}
    body = (await client.get(MODELS, params=params)).json()

    assert names(body) == ["active", "inactive"]
    assert body["total"] == 2


# ---------------------------------------------------------------
# 정렬
# ---------------------------------------------------------------
async def test_정렬_기준과_방향을_바꿀_수_있다(
    client: AsyncClient, factory: Factory
) -> None:
    for display_name in ("b", "a", "c"):
        await factory.model(display_name=display_name)

    ascending = await client.get(
        MODELS, params={"sort": "display_name", "order": "asc"}
    )
    descending = await client.get(
        MODELS, params={"sort": "display_name", "order": "desc"}
    )

    assert names(ascending.json()) == ["a", "b", "c"]
    assert names(descending.json()) == ["c", "b", "a"]


async def test_기본_정렬은_최근_등록순이다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model(display_name="먼저", created_at=T0)
    await factory.model(display_name="나중", created_at=T0 + timedelta(days=1))

    body = (await client.get(MODELS)).json()

    assert names(body) == ["나중", "먼저"]


async def test_가격으로_정렬하면_가격이_없는_모델은_항상_뒤에_둔다(
    client: AsyncClient, factory: Factory
) -> None:
    cheap = await factory.model(display_name="싼 모델")
    pricey = await factory.model(display_name="비싼 모델")
    await factory.model(display_name="가격 없음")
    await factory.model_price(
        model_id=cheap["model_id"], input_price_per_token=Decimal("0.1")
    )
    await factory.model_price(
        model_id=pricey["model_id"], input_price_per_token=Decimal("0.9")
    )

    ascending = await client.get(MODELS, params={"sort": "price_input", "order": "asc"})
    descending = await client.get(
        MODELS, params={"sort": "price_input", "order": "desc"}
    )

    assert names(ascending.json()) == ["싼 모델", "비싼 모델", "가격 없음"]
    assert names(descending.json()) == ["비싼 모델", "싼 모델", "가격 없음"]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "password_hash"},
        {"sort": "display_name; DROP TABLE models"},
        {"order": "sideways"},
        {"status": "DELETED"},
        {"unknown_param": "1"},
    ],
)
async def test_허용하지_않는_조건은_422이다(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(MODELS, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------
async def test_페이지로_나누어_total은_전체_개수를_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    for number in range(1, 4):
        await factory.model(display_name=f"model {number}")
    base = {"sort": "display_name", "order": "asc", "page_size": 2}

    first = (await client.get(MODELS, params={**base, "page": 1})).json()
    second = (await client.get(MODELS, params={**base, "page": 2})).json()

    assert names(first) == ["model 1", "model 2"]
    assert names(second) == ["model 3"]
    assert first["total"] == second["total"] == 3
    assert (second["page"], second["page_size"]) == (2, 2)


async def test_마지막_페이지를_넘으면_빈_목록이고_total은_그대로다(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.model()

    body = (await client.get(MODELS, params={"page": 5})).json()

    assert body["items"] == []
    assert body["total"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": MAX_PAGE_SIZE + 1},
    ],
)
async def test_페이지_범위를_벗어나면_422이다(
    client: AsyncClient, params: dict[str, int]
) -> None:
    response = await client.get(MODELS, params=params)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_한_페이지_최대_개수는_허용한다(client: AsyncClient) -> None:
    response = await client.get(MODELS, params={"page_size": MAX_PAGE_SIZE})

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    ("page", "expected_status"),
    [
        (MAX_PAGE, status.HTTP_200_OK),
        (MAX_PAGE + 1, status.HTTP_422_UNPROCESSABLE_CONTENT),
    ],
)
async def test_page의_상한_경계(
    client: AsyncClient, page: int, expected_status: int
) -> None:
    params = {"page": page, "page_size": MAX_PAGE_SIZE}

    response = await client.get(MODELS, params=params)

    assert response.status_code == expected_status


@pytest.mark.parametrize("name", ["q", "name", "model_id", "provider"])
async def test_검색어에_NUL_문자가_있으면_422이다(
    client: AsyncClient, name: str
) -> None:
    response = await client.get(MODELS, params={name: "a\x00b"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------
# 상세 조회
# ---------------------------------------------------------------
def detail_url(model_id: object) -> str:
    return f"{MODELS}/{model_id}"


async def test_상세는_목록의_한_줄과_같은_값을_돌려준다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(
        display_name="상세",
        purpose="요약",
        input_modalities=["text"],
        supported_parameters=["response_format"],
    )
    await factory.model_price(
        model_id=model["model_id"], input_price_per_token=Decimal("0.000002")
    )

    listed = (await client.get(MODELS)).json()["items"][0]
    response = await client.get(detail_url(model["model_id"]))

    assert response.status_code == status.HTTP_200_OK
    detail = response.json()
    assert {key: detail[key] for key in listed} == listed


async def test_상세에는_활성화_비활성화_성공_테스트_시각이_더해진다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model(
        status="INACTIVE",
        activated_at=T0,
        deactivated_at=T0 + timedelta(days=1),
        last_success_test_at=T0 + timedelta(hours=1),
    )

    detail = (await client.get(detail_url(model["model_id"]))).json()

    assert datetime.fromisoformat(detail["activated_at"]) == T0
    assert datetime.fromisoformat(detail["deactivated_at"]) == T0 + timedelta(days=1)
    assert datetime.fromisoformat(detail["last_success_test_at"]) == T0 + timedelta(
        hours=1
    )


async def test_시각이_없으면_상세의_해당_칸은_null이다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()

    detail = (await client.get(detail_url(model["model_id"]))).json()

    assert detail["activated_at"] is None
    assert detail["deactivated_at"] is None
    assert detail["last_success_test_at"] is None


async def test_상세의_현재_가격은_종료되지_않은_대표가격이다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()
    model_id = model["model_id"]
    day = timedelta(days=1)
    await factory.model_price(
        model_id=model_id,
        input_price_per_token=Decimal("0.1"),
        effective_to=T0 + day,
    )
    await factory.model_price(
        model_id=model_id,
        input_price_per_token=Decimal("0.2"),
        effective_from=T0 + day,
    )
    await factory.model_price(
        model_id=model_id,
        execution_provider="SomeProvider",
        input_price_per_token=Decimal("0.3"),
        effective_from=T0 + day,
    )

    price = (await client.get(detail_url(model_id))).json()["current_price"]

    assert Decimal(price["input_price_per_token"]) == Decimal("0.2")
    assert price["execution_provider"] is None


async def test_가격이_없는_모델의_상세는_current_price가_null이다(
    client: AsyncClient, factory: Factory
) -> None:
    model = await factory.model()

    detail = (await client.get(detail_url(model["model_id"]))).json()

    assert detail["current_price"] is None


@pytest.mark.parametrize("model_id", [1, 999999, MAX_MODEL_ID])
async def test_없는_모델_번호는_404이다(client: AsyncClient, model_id: int) -> None:
    response = await client.get(detail_url(model_id))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "모델을 찾을 수 없습니다.",
    }


@pytest.mark.parametrize(
    "model_id",
    ["abc", "0", "-1", "1.5", str(MAX_MODEL_ID + 1), "99999999999999999999"],
)
async def test_올바르지_않은_모델_번호는_422이다(
    client: AsyncClient, model_id: str
) -> None:
    response = await client.get(detail_url(model_id))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "VALIDATION_ERROR"

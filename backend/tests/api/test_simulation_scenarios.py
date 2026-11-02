"""GET /api/scenarios 테스트. 시뮬레이터(P-04)와 이력 필터(P-05)가 고를 시나리오 목록을 준다."""

import pytest
from httpx import AsyncClient

from app.models import InputType
from tests.db_helpers import Factory

SCENARIOS = "/api/scenarios"


async def listed_ids(client: AsyncClient, **params: object) -> list[int]:
    response = await client.get(SCENARIOS, params=params)
    assert response.status_code == 200, response.text
    return [item["scenario_id"] for item in response.json()["items"]]


@pytest.mark.usefixtures("signed_in")
async def test_a_scenario_carries_what_the_screen_needs_and_nothing_else(
    client: AsyncClient, factory: Factory
) -> None:
    schema = {"type": "object", "required": ["color"]}
    config = {"temperature": 0.2, "max_tokens": 512}
    row = await factory.scenario(
        scenario_code="PRODUCT_COPY",
        name="상품 문구",
        description="상품 문구 작성",
        input_type="TEXT_IMAGE",
        prompt_template="{{product_name}} 문구를 쓰세요",
        default_json_schema=schema,
        default_execution_config=config,
    )

    response = await client.get(SCENARIOS)

    assert response.status_code == 200
    # 키 전체를 비교해 서버 전용 값(생성·수정 시각 등)이 새 나가지 않는지도 함께 확인한다
    assert response.json() == {
        "items": [
            {
                "scenario_id": row["scenario_id"],
                "scenario_code": "PRODUCT_COPY",
                "name": "상품 문구",
                "description": "상품 문구 작성",
                "input_type": "TEXT_IMAGE",
                "prompt_template": "{{product_name}} 문구를 쓰세요",
                "default_json_schema": schema,
                "default_execution_config": config,
                "is_active": True,
            }
        ]
    }


@pytest.mark.usefixtures("signed_in")
async def test_optional_values_stay_empty_when_the_scenario_has_none(
    client: AsyncClient, factory: Factory
) -> None:
    await factory.scenario()

    item = (await client.get(SCENARIOS)).json()["items"][0]

    assert item["description"] is None
    assert item["default_json_schema"] is None
    assert item["default_execution_config"] == {}


@pytest.mark.usefixtures("signed_in")
async def test_no_scenarios_gives_an_empty_list(client: AsyncClient) -> None:
    assert await listed_ids(client) == []


@pytest.mark.usefixtures("signed_in")
async def test_inactive_scenarios_appear_only_when_asked_for(
    client: AsyncClient, factory: Factory
) -> None:
    active = (await factory.scenario())["scenario_id"]
    inactive = (await factory.scenario(is_active=False))["scenario_id"]

    assert await listed_ids(client) == [active]
    assert await listed_ids(client, include_inactive="false") == [active]
    assert await listed_ids(client, include_inactive="true") == [active, inactive]


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize("input_type", list(InputType))
async def test_every_input_type_is_returned_as_stored(
    client: AsyncClient, factory: Factory, input_type: InputType
) -> None:
    await factory.scenario(input_type=input_type.value)

    item = (await client.get(SCENARIOS)).json()["items"][0]

    assert item["input_type"] == input_type.value


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize(
    "params", [{"include_inactive": "maybe"}, {"unknown_condition": "1"}]
)
async def test_invalid_conditions_are_refused_with_the_error_format(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get(SCENARIOS, params=params)

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
async def test_scenarios_can_only_be_read(client: AsyncClient, method: str) -> None:
    response = await client.request(method.upper(), SCENARIOS)

    assert response.status_code == 405

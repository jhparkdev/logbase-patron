"""/api/model-favorites 테스트. 첫 활성 계정의 모델+Provider 즐겨찾기 계약을 확인한다."""

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models import UserModelFavorite
from tests.api.test_auth import log_in, make_user
from tests.db_helpers import Factory

FAVORITES = "/api/model-favorites"
PROVIDER = "DeepInfra"
OTHER_PROVIDER = "DekaLLM"
MISSING_MODEL_ID = 2_000_000_000


async def add(client: AsyncClient, model_id: int, provider: str) -> Response:
    return await client.post(
        FAVORITES, json={"model_id": model_id, "execution_provider": provider}
    )


async def remove(client: AsyncClient, model_id: int, provider: str) -> Response:
    return await client.delete(
        FAVORITES, params={"model_id": model_id, "execution_provider": provider}
    )


async def listed(client: AsyncClient) -> list[tuple[int, str]]:
    response = await client.get(FAVORITES)
    assert response.status_code == 200, response.text
    return [
        (item["model_id"], item["execution_provider"])
        for item in response.json()["items"]
    ]


async def new_model_id(factory: Factory) -> int:
    return int((await factory.model())["model_id"])


async def test_every_route_works_without_a_login_session(
    client: AsyncClient, factory: Factory
) -> None:
    # 팀 결정으로 로그인 검사를 하지 않는다. 즐겨찾기는 첫 활성 계정의 것으로 다룬다
    await make_user(factory)
    model_id = await new_model_id(factory)

    assert (await add(client, model_id, PROVIDER)).status_code == 201
    assert await listed(client) == [(model_id, PROVIDER)]
    assert (await remove(client, model_id, PROVIDER)).status_code == 204
    assert await listed(client) == []


async def test_without_an_active_account_every_route_is_refused(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)

    for response in (
        await client.get(FAVORITES),
        await add(client, model_id, PROVIDER),
        await remove(client, model_id, PROVIDER),
    ):
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.usefixtures("signed_in")
async def test_a_user_with_no_favorites_gets_an_empty_list(
    client: AsyncClient,
) -> None:
    assert await listed(client) == []


@pytest.mark.usefixtures("signed_in")
async def test_adding_a_favorite_returns_it_and_lists_it(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)

    response = await add(client, model_id, PROVIDER)

    assert response.status_code == 201
    body = response.json()
    assert body["model_id"] == model_id
    assert body["execution_provider"] == PROVIDER
    assert body["created_at"]
    assert await listed(client) == [(model_id, PROVIDER)]


@pytest.mark.usefixtures("signed_in")
async def test_adding_the_same_favorite_again_changes_nothing(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)
    first = await add(client, model_id, PROVIDER)

    again = await add(client, model_id, PROVIDER)

    assert again.status_code == 200
    assert again.json() == first.json()
    assert await listed(client) == [(model_id, PROVIDER)]


@pytest.mark.usefixtures("signed_in")
async def test_the_same_model_with_another_provider_is_a_separate_favorite(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)

    await add(client, model_id, PROVIDER)
    await add(client, model_id, OTHER_PROVIDER)

    # 같은 시각(테스트는 한 트랜잭션)이면 Provider 이름순으로 고정된다
    assert await listed(client) == [
        (model_id, PROVIDER),
        (model_id, OTHER_PROVIDER),
    ]


@pytest.mark.usefixtures("signed_in")
async def test_surrounding_spaces_in_the_provider_are_trimmed(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)

    response = await add(client, model_id, f"  {PROVIDER} ")

    assert response.status_code == 201
    assert response.json()["execution_provider"] == PROVIDER


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize("provider", ["", "   "])
async def test_a_blank_provider_is_rejected(
    client: AsyncClient, factory: Factory, provider: str
) -> None:
    model_id = await new_model_id(factory)

    response = await add(client, model_id, provider)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert await listed(client) == []


@pytest.mark.usefixtures("signed_in")
async def test_an_unknown_model_is_rejected_without_a_server_error(
    client: AsyncClient,
) -> None:
    response = await add(client, MISSING_MODEL_ID, PROVIDER)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert await listed(client) == []


@pytest.mark.usefixtures("signed_in")
async def test_removing_a_favorite_deletes_only_that_pair(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)
    await add(client, model_id, PROVIDER)
    await add(client, model_id, OTHER_PROVIDER)

    response = await remove(client, model_id, PROVIDER)

    assert response.status_code == 204
    assert await listed(client) == [(model_id, OTHER_PROVIDER)]


@pytest.mark.usefixtures("signed_in")
async def test_removing_a_favorite_that_does_not_exist_is_not_an_error(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)

    assert (await remove(client, model_id, PROVIDER)).status_code == 204
    assert (await remove(client, MISSING_MODEL_ID, PROVIDER)).status_code == 204


async def test_favorites_belong_to_the_first_active_account_whoever_is_logged_in(
    client: AsyncClient, factory: Factory, signed_in: dict[str, Any]
) -> None:
    # 지금은 계정 하나만 쓰므로 누가 로그인했든 같은 즐겨찾기를 본다
    model_id = await new_model_id(factory)
    await add(client, model_id, PROVIDER)
    other = await make_user(factory)
    assert (await log_in(client, other["email"])).status_code == 200

    assert await listed(client) == [(model_id, PROVIDER)]
    owners = await factory.session.scalars(
        select(UserModelFavorite.user_id).where(UserModelFavorite.model_id == model_id)
    )
    assert owners.all() == [signed_in["user_id"]]


@pytest.mark.usefixtures("signed_in")
async def test_a_favorite_survives_the_model_being_deactivated(
    client: AsyncClient, factory: Factory
) -> None:
    # 모델이 비활성이 되어도 이력은 지우지 않는다. 화면이 상태를 보고 선택 가능 여부를 정한다
    model_id = int((await factory.model(status="INACTIVE"))["model_id"])

    assert (await add(client, model_id, PROVIDER)).status_code == 201
    assert await listed(client) == [(model_id, PROVIDER)]


@pytest.mark.usefixtures("signed_in")
async def test_a_state_changing_request_from_another_origin_is_refused(
    client: AsyncClient, factory: Factory
) -> None:
    model_id = await new_model_id(factory)

    response = await client.post(
        FAVORITES,
        json={"model_id": model_id, "execution_provider": PROVIDER},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"

"""services/model_new.py 테스트. 최근에 올라왔고 아직 등록하지 않은 OpenRouter 모델만 찾는다."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.openrouter.lookup_result import ModelInfo
from app.services.model_new import find_new_models
from tests.api.model_helpers import info
from tests.db_helpers import T0, Factory

NOW = T0 + timedelta(days=100)
DAYS = 30


def made(model_id: str, age: timedelta | None) -> ModelInfo:
    """age만큼 전에 올라온 모델. age가 None이면 올라온 시각을 모르는 모델이다."""
    return info(model_id, created_at=None if age is None else NOW - age)


async def ids_of(
    session: AsyncSession, models: list[ModelInfo], limit: int = 100
) -> list[str]:
    found = await find_new_models(session, models, now=NOW, days=DAYS, limit=limit)
    return [entry.model.model_id for entry in found.items]


async def test_기간_경계_바로_전과_정확히_그_값은_포함하고_바로_후는_뺀다(
    db_session: AsyncSession,
) -> None:
    limit = timedelta(days=DAYS)
    models = [
        made("a/just-inside", limit - timedelta(seconds=1)),
        made("a/exactly", limit),
        made("a/just-outside", limit + timedelta(seconds=1)),
    ]

    assert await ids_of(db_session, models) == ["a/just-inside", "a/exactly"]


async def test_올라온_시각을_모르는_모델은_뺀다(db_session: AsyncSession) -> None:
    models = [made("a/known", timedelta(days=1)), made("a/unknown", None)]

    assert await ids_of(db_session, models) == ["a/known"]


async def test_이미_등록된_모델은_뺀다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.model(openrouter_model_id="a/registered")
    models = [made("a/registered", timedelta(days=1)), made("a/new", timedelta(days=1))]

    assert await ids_of(db_session, models) == ["a/new"]


async def test_등록하지_않은_기간_밖_모델은_그대로_뺀다(
    db_session: AsyncSession,
) -> None:
    assert await ids_of(db_session, [made("a/old", timedelta(days=200))]) == []


async def test_최근에_올라온_순이고_같은_시각이면_모델_ID순이다(
    db_session: AsyncSession,
) -> None:
    models = [
        made("a/older", timedelta(days=5)),
        made("c/same", timedelta(days=2)),
        made("a/newest", timedelta(days=1)),
        made("b/same", timedelta(days=2)),
    ]

    assert await ids_of(db_session, models) == [
        "a/newest",
        "b/same",
        "c/same",
        "a/older",
    ]


async def test_개수를_제한해도_전체_개수는_조건에_맞는_모두이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    await factory.model(openrouter_model_id="a/registered")
    models = [made(f"a/m{number}", timedelta(days=number)) for number in range(1, 6)]
    models.append(made("a/registered", timedelta(days=1)))

    found = await find_new_models(db_session, models, now=NOW, days=DAYS, limit=2)

    assert [entry.model.model_id for entry in found.items] == ["a/m1", "a/m2"]
    assert found.total == 5


async def test_모델이_없으면_빈_결과이다(db_session: AsyncSession) -> None:
    found = await find_new_models(db_session, [], now=NOW, days=DAYS, limit=5)

    assert (found.items, found.total) == ([], 0)

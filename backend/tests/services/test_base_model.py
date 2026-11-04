"""services/base_model.py 테스트. 최근 고객 서비스 호출이 가장 많은 모델을 기본 모델로 찾는다."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.base_model import find_base_model
from tests.db_helpers import T0, Factory

NOW = T0 + timedelta(days=100)
SINCE = NOW - timedelta(days=30)
RECENT = NOW - timedelta(days=1)


async def customer_call(factory: Factory, model_id: int | None, **values: object):
    customer = await factory.customer()
    key = await factory.api_key(
        owner_type="CUSTOMER", customer_id=customer["customer_id"]
    )
    return await factory.ai_request(
        **{
            "usage_origin": "CUSTOMER_SERVICE",
            "customer_id": customer["customer_id"],
            "key_id": key["key_id"],
            "model_id": model_id,
            "status": "SUCCESS",
            "requested_at": RECENT,
            **values,
        }
    )


async def test_고객_호출이_가장_많은_모델이_기본_모델이다(
    db_session: AsyncSession, factory: Factory
) -> None:
    popular = await factory.model(openrouter_model_id="a/popular")
    rare = await factory.model(openrouter_model_id="a/rare")
    for _ in range(3):
        await customer_call(factory, popular["model_id"])
    await customer_call(factory, rare["model_id"])

    found = await find_base_model(db_session, since=SINCE)

    assert found is not None
    assert found.model_id == popular["model_id"]
    assert found.openrouter_model_id == "a/popular"
    assert found.call_count == 3


async def test_호출이_없으면_기본_모델도_없다(db_session: AsyncSession) -> None:
    assert await find_base_model(db_session, since=SINCE) is None


async def test_기간_밖의_호출과_성공이_아닌_호출은_세지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    old = await factory.model()
    failed = await factory.model()
    await customer_call(
        factory, old["model_id"], requested_at=SINCE - timedelta(days=1)
    )
    await customer_call(
        factory,
        failed["model_id"],
        status="FAILED",
        error_type="UNKNOWN_ERROR",
        http_status=500,
    )

    assert await find_base_model(db_session, since=SINCE) is None


async def test_고객_호출이_아닌_이력과_모델이_없는_호출은_세지_않는다(
    db_session: AsyncSession, factory: Factory
) -> None:
    internal = await factory.model()
    await factory.ai_request(
        usage_origin="INTERNAL_DEVELOPMENT",
        model_id=internal["model_id"],
        status="SUCCESS",
        requested_at=RECENT,
    )
    await customer_call(factory, None)

    assert await find_base_model(db_session, since=SINCE) is None


async def test_호출_수가_같으면_모델_번호가_작은_쪽을_고른다(
    db_session: AsyncSession, factory: Factory
) -> None:
    first = await factory.model()
    second = await factory.model()
    await customer_call(factory, second["model_id"])
    await customer_call(factory, first["model_id"])

    found = await find_base_model(db_session, since=SINCE)

    assert found is not None
    assert found.model_id == first["model_id"]


async def test_평균_토큰은_토큰을_아는_호출만으로_구한다(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model()
    await customer_call(
        factory, model["model_id"], input_tokens=1000, output_tokens=200
    )
    await customer_call(
        factory, model["model_id"], input_tokens=3000, output_tokens=400
    )
    await customer_call(factory, model["model_id"])

    found = await find_base_model(db_session, since=SINCE)

    assert found is not None
    assert found.call_count == 3
    assert found.avg_input_tokens == 2000
    assert found.avg_output_tokens == 300


async def test_토큰을_아는_호출이_없으면_평균_토큰도_모른다(
    db_session: AsyncSession, factory: Factory
) -> None:
    model = await factory.model()
    await customer_call(factory, model["model_id"])

    found = await find_base_model(db_session, since=SINCE)

    assert found is not None
    assert found.avg_input_tokens is None
    assert found.avg_output_tokens is None

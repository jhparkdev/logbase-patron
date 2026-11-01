from datetime import UTC, datetime, timedelta

import pytest

from app.openrouter.errors import ErrorType
from app.openrouter.lookup_result import LookupResult, ModelInfo
from app.services.openrouter_catalog import (
    CACHE_TTL,
    OpenRouterCatalog,
    OpenRouterUnavailableError,
)

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)
FAILED: LookupResult[list[ModelInfo]] = LookupResult(error_type=ErrorType.NETWORK_ERROR)


def model(model_id: str) -> ModelInfo:
    return ModelInfo(
        model_id=model_id,
        pricing={},
        input_modalities=["text"],
        supported_parameters=[],
    )


def received(*model_ids: str) -> LookupResult[list[ModelInfo]]:
    return LookupResult(data=[model(model_id) for model_id in model_ids])


class FakeSource:
    """OpenRouter 대신 정해 둔 결과를 순서대로 돌려주고, 몇 번 불렸는지 센다."""

    def __init__(self, *results: LookupResult[list[ModelInfo]]) -> None:
        self.results = list(results)
        self.calls = 0

    async def fetch(self) -> LookupResult[list[ModelInfo]]:
        self.calls += 1
        return self.results.pop(0)


class FakeClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def ids(models: list[ModelInfo]) -> list[str]:
    return [item.model_id for item in models]


async def test_처음에는_OpenRouter에서_목록을_받아_온다() -> None:
    source = FakeSource(received("a/b"))
    catalog = OpenRouterCatalog(source.fetch, FakeClock())

    models = await catalog.get()

    assert ids(models) == ["a/b"]
    assert source.calls == 1


@pytest.mark.parametrize(
    ("elapsed", "expected_calls"),
    [(CACHE_TTL - SECOND, 1), (CACHE_TTL, 2), (CACHE_TTL + SECOND, 2)],
    ids=["10분 1초 전", "정확히 10분", "10분 1초 뒤"],
)
async def test_보관한_목록은_10분이_지나야_다시_받는다(
    elapsed: timedelta, expected_calls: int
) -> None:
    source = FakeSource(received("a/b"), received("c/d"))
    clock = FakeClock()
    catalog = OpenRouterCatalog(source.fetch, clock)
    await catalog.get()

    clock.now = T0 + elapsed
    await catalog.get()

    assert source.calls == expected_calls


async def test_다시_받으면_새_목록으로_바뀐다() -> None:
    source = FakeSource(received("a/b"), received("c/d"))
    clock = FakeClock()
    catalog = OpenRouterCatalog(source.fetch, clock)
    await catalog.get()

    clock.now = T0 + CACHE_TTL
    models = await catalog.get()

    assert ids(models) == ["c/d"]


async def test_새로_받지_못하면_보관한_목록을_그대로_쓴다() -> None:
    source = FakeSource(received("a/b"), FAILED)
    clock = FakeClock()
    catalog = OpenRouterCatalog(source.fetch, clock)
    await catalog.get()

    clock.now = T0 + CACHE_TTL
    models = await catalog.get()

    assert ids(models) == ["a/b"]
    assert source.calls == 2


async def test_보관한_목록이_없는데_받지_못하면_예외를_던진다() -> None:
    catalog = OpenRouterCatalog(FakeSource(FAILED).fetch, FakeClock())

    with pytest.raises(OpenRouterUnavailableError):
        await catalog.get()


async def test_빈_목록은_받지_못한_것으로_본다() -> None:
    catalog = OpenRouterCatalog(FakeSource(received()).fetch, FakeClock())

    with pytest.raises(OpenRouterUnavailableError):
        await catalog.get()


async def test_받지_못한_뒤_다시_받으면_복구한다() -> None:
    source = FakeSource(FAILED, received("a/b"))
    catalog = OpenRouterCatalog(source.fetch, FakeClock())
    with pytest.raises(OpenRouterUnavailableError):
        await catalog.get()

    models = await catalog.get()

    assert ids(models) == ["a/b"]

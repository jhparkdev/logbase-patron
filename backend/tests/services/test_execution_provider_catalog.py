from datetime import UTC, datetime, timedelta

import pytest

from app.openrouter.errors import ErrorType
from app.openrouter.lookup_result import EndpointInfo, LookupResult
from app.services.execution_provider_catalog import (
    CACHE_TTL,
    EndpointCatalog,
    ModelNotOnOpenRouterError,
)
from app.services.openrouter_catalog import OpenRouterUnavailableError

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)
NETWORK_FAILURE: LookupResult[list[EndpointInfo]] = LookupResult(
    error_type=ErrorType.NETWORK_ERROR
)
NOT_FOUND: LookupResult[list[EndpointInfo]] = LookupResult(
    error_type=ErrorType.UNKNOWN_ERROR, http_status=404
)


def received(*names: str) -> LookupResult[list[EndpointInfo]]:
    return LookupResult(data=[EndpointInfo(provider_name=name) for name in names])


class FakeSource:
    """OpenRouter 대신 정해 둔 결과를 순서대로 돌려주고, 어느 모델을 몇 번 물었는지 센다."""

    def __init__(self, *results: LookupResult[list[EndpointInfo]]) -> None:
        self.results = list(results)
        self.asked: list[str] = []

    async def fetch(self, model_id: str) -> LookupResult[list[EndpointInfo]]:
        self.asked.append(model_id)
        return self.results.pop(0)


class FakeClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def names(endpoints: list[EndpointInfo]) -> list[str]:
    return [item.provider_name for item in endpoints]


async def test_처음에는_OpenRouter에서_모델_ID로_받아_온다() -> None:
    source = FakeSource(received("DekaLLM", "Io Net"))
    catalog = EndpointCatalog(source.fetch, FakeClock())

    endpoints = await catalog.get("a/b")

    assert names(endpoints) == ["DekaLLM", "Io Net"]
    assert source.asked == ["a/b"]


@pytest.mark.parametrize(
    ("elapsed", "expected_calls"),
    [(CACHE_TTL - SECOND, 1), (CACHE_TTL, 2), (CACHE_TTL + SECOND, 2)],
    ids=["10분 1초 전", "정확히 10분", "10분 1초 뒤"],
)
async def test_보관한_목록은_10분이_지나야_다시_받는다(
    elapsed: timedelta, expected_calls: int
) -> None:
    clock = FakeClock()
    source = FakeSource(received("DekaLLM"), received("DekaLLM"))
    catalog = EndpointCatalog(source.fetch, clock)
    await catalog.get("a/b")

    clock.now = T0 + elapsed
    await catalog.get("a/b")

    assert len(source.asked) == expected_calls


async def test_모델마다_따로_보관한다() -> None:
    source = FakeSource(received("DekaLLM"), received("Parasail"))
    catalog = EndpointCatalog(source.fetch, FakeClock())

    first = await catalog.get("a/b")
    second = await catalog.get("c/d")
    again = await catalog.get("a/b")

    assert names(first) == ["DekaLLM"]
    assert names(second) == ["Parasail"]
    assert names(again) == ["DekaLLM"]
    assert source.asked == ["a/b", "c/d"]


async def test_정상_응답의_빈_목록은_그대로_돌려주고_보관한다() -> None:
    source = FakeSource(received())
    catalog = EndpointCatalog(source.fetch, FakeClock())

    first = await catalog.get("a/b")
    second = await catalog.get("a/b")

    assert (first, second) == ([], [])
    assert len(source.asked) == 1


async def test_받지_못했고_보관한_것도_없으면_조회_실패다() -> None:
    source = FakeSource(NETWORK_FAILURE)
    catalog = EndpointCatalog(source.fetch, FakeClock())

    with pytest.raises(OpenRouterUnavailableError):
        await catalog.get("a/b")


async def test_실패는_보관하지_않고_다음_요청에서_다시_받는다() -> None:
    source = FakeSource(NETWORK_FAILURE, received("DekaLLM"))
    catalog = EndpointCatalog(source.fetch, FakeClock())
    with pytest.raises(OpenRouterUnavailableError):
        await catalog.get("a/b")

    endpoints = await catalog.get("a/b")

    assert names(endpoints) == ["DekaLLM"]


async def test_10분이_지나_다시_받지_못하면_보관한_목록을_그대로_쓴다() -> None:
    clock = FakeClock()
    source = FakeSource(received("DekaLLM"), NETWORK_FAILURE)
    catalog = EndpointCatalog(source.fetch, clock)
    await catalog.get("a/b")

    clock.now = T0 + CACHE_TTL + SECOND
    endpoints = await catalog.get("a/b")

    assert names(endpoints) == ["DekaLLM"]


async def test_OpenRouter에_모델이_없으면_없다고_알린다() -> None:
    source = FakeSource(NOT_FOUND)
    catalog = EndpointCatalog(source.fetch, FakeClock())

    with pytest.raises(ModelNotOnOpenRouterError):
        await catalog.get("a/gone")


async def test_모델이_없다는_응답이_오면_보관한_목록은_쓰지_않는다() -> None:
    clock = FakeClock()
    source = FakeSource(received("DekaLLM"), NOT_FOUND, NETWORK_FAILURE)
    catalog = EndpointCatalog(source.fetch, clock)
    await catalog.get("a/b")

    clock.now = T0 + CACHE_TTL + SECOND
    with pytest.raises(ModelNotOnOpenRouterError):
        await catalog.get("a/b")

    # 보관한 목록이 지워졌으므로, 다음 실패에서 옛 목록이 돌아오지 않는다.
    with pytest.raises(OpenRouterUnavailableError):
        await catalog.get("a/b")

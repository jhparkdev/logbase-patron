import pytest

from app.openrouter.lookup_result import ModelInfo
from app.services.model_search import search_models


def model(model_id: str, name: str | None = None) -> ModelInfo:
    return ModelInfo(
        model_id=model_id,
        name=name,
        pricing={},
        input_modalities=["text"],
        supported_parameters=[],
    )


def ids(items: list[ModelInfo]) -> list[str]:
    return [item.model_id for item in items]


MODELS = [
    model("openai/gpt-x", name="OpenAI: GPT X"),
    model("acme/unique-id", name="Big Name"),
    model("vendor/100%", name=None),
]


def test_검색어가_없으면_모델_ID순으로_전체를_돌려준다() -> None:
    page = search_models(MODELS, q=None, page=1, page_size=10)

    assert ids(page.items) == ["acme/unique-id", "openai/gpt-x", "vendor/100%"]
    assert page.total == 3


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("gpt-x", ["openai/gpt-x"]),
        ("UNIQUE", ["acme/unique-id"]),
        ("big name", ["acme/unique-id"]),
        ("OPENAI: gpt", ["openai/gpt-x"]),
        ("없는 모델", []),
    ],
    ids=["모델 ID", "대문자", "이름", "이름의 일부", "없는 글자"],
)
def test_검색어가_모델_ID나_이름에_들어_있으면_찾는다(
    q: str, expected: list[str]
) -> None:
    page = search_models(MODELS, q=q, page=1, page_size=10)

    assert ids(page.items) == expected
    assert page.total == len(expected)


def test_이름이_없는_모델도_모델_ID로_찾는다() -> None:
    page = search_models(MODELS, q="100%", page=1, page_size=10)

    assert ids(page.items) == ["vendor/100%"]


def test_페이지로_나누고_total은_찾은_전체_개수이다() -> None:
    first = search_models(MODELS, q=None, page=1, page_size=2)
    second = search_models(MODELS, q=None, page=2, page_size=2)

    assert ids(first.items) == ["acme/unique-id", "openai/gpt-x"]
    assert ids(second.items) == ["vendor/100%"]
    assert first.total == second.total == 3


def test_마지막_페이지를_넘으면_빈_목록이고_total은_그대로이다() -> None:
    page = search_models(MODELS, q=None, page=5, page_size=2)

    assert page.items == []
    assert page.total == 3

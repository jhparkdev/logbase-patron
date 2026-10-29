from decimal import Decimal
from typing import Any

import pytest

from app.openrouter.streaming import (
    DONE_PAYLOAD,
    GenerationIdTracker,
    find_stream_error,
    get_data_payload,
    merge_chunks,
    parse_chunk,
)

CHUNKS: list[dict[str, Any]] = [
    {
        "id": "gen-s1",
        "model": "mistralai/mistral-nemo",
        "provider": "DekaLLM",
        "choices": [{"delta": {"role": "assistant", "content": "안"}}],
    },
    {
        "id": "gen-s1",
        "model": "mistralai/mistral-nemo",
        "provider": "DekaLLM",
        "choices": [{"delta": {"content": "녕"}, "finish_reason": "stop"}],
    },
    {
        "id": "gen-s1",
        "model": "mistralai/mistral-nemo",
        "provider": "DekaLLM",
        "choices": [],
        "usage": {"prompt_tokens": 16, "completion_tokens": 2, "cost": 3.48e-07},
    },
]


# ---------------------------------------------------------------
# SSE 줄 읽기
# ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('data: {"a": 1}', '{"a": 1}'),
        ('data:{"a": 1}', '{"a": 1}'),
        ("data: [DONE]", DONE_PAYLOAD),
        (": OPENROUTER PROCESSING", None),
        ("", None),
        ("event: message", None),
    ],
)
def test_data_줄만_내용을_꺼내고_주석과_빈_줄은_무시한다(
    line: str, expected: str | None
) -> None:
    assert get_data_payload(line) == expected


def test_조각은_JSON_객체로_읽고_소수는_Decimal로_읽는다() -> None:
    chunk = parse_chunk('{"usage": {"cost": 3.48e-07}}')

    assert chunk == {"usage": {"cost": Decimal("3.48e-07")}}


@pytest.mark.parametrize("payload", ["{not json", "[1, 2]", '"text"', ""])
def test_JSON_객체가_아닌_조각은_None이다(payload: str) -> None:
    assert parse_chunk(payload) is None


# ---------------------------------------------------------------
# 조각 합치기
# ---------------------------------------------------------------
def test_조각의_내용을_이어_붙여_일반_응답_모양으로_합친다() -> None:
    body = merge_chunks(CHUNKS)

    assert body["id"] == "gen-s1"
    assert body["model"] == "mistralai/mistral-nemo"
    assert body["provider"] == "DekaLLM"
    assert body["choices"] == [
        {
            "message": {"role": "assistant", "content": "안녕"},
            "finish_reason": "stop",
        }
    ]
    assert body["usage"] == {
        "prompt_tokens": 16,
        "completion_tokens": 2,
        "cost": 3.48e-07,
    }


def test_내용이_없는_조각이_섞여_있어도_합친다() -> None:
    chunks: list[dict[str, Any]] = [
        {"choices": [{"delta": {"role": "assistant", "content": None}}]},
        {"choices": [{"delta": {}}]},
        {"choices": [{"delta": {"content": "답"}}]},
    ]

    body = merge_chunks(chunks)

    assert body["choices"][0]["message"]["content"] == "답"
    assert body["choices"][0]["finish_reason"] is None
    assert "usage" not in body


def test_조각이_없으면_내용이_빈_본문이다() -> None:
    body = merge_chunks([])

    assert body["choices"][0]["message"]["content"] == ""
    assert "id" not in body


def test_스트림_중간에_온_오류를_찾는다() -> None:
    error = {"code": 502, "message": "provider disconnected"}

    assert find_stream_error([*CHUNKS, {"error": error}]) == error
    assert find_stream_error(CHUNKS) is None


# ---------------------------------------------------------------
# 호출 ID 알림
# ---------------------------------------------------------------
class IdRecorder:
    def __init__(self) -> None:
        self.received: list[str] = []

    async def __call__(self, generation_id: str) -> None:
        self.received.append(generation_id)


async def test_호출_ID를_처음_알게_된_순간_한_번만_콜백에_알린다() -> None:
    recorder = IdRecorder()
    tracker = GenerationIdTracker(recorder)

    await tracker.note("gen-first")
    await tracker.note("gen-second")

    assert recorder.received == ["gen-first"]
    assert tracker.generation_id == "gen-first"


@pytest.mark.parametrize(
    "invalid", [None, "", "not-an-id", "gen-", "gen-abc 123", "gen-" + "a" * 200]
)
async def test_형식이_틀린_호출_ID는_무시하고_다음_값을_기다린다(
    invalid: str | None,
) -> None:
    recorder = IdRecorder()
    tracker = GenerationIdTracker(recorder)

    await tracker.note(invalid)
    assert tracker.generation_id is None
    assert recorder.received == []

    await tracker.note("gen-valid")
    assert recorder.received == ["gen-valid"]


async def test_콜백이_실패해도_호출_ID는_기억하고_예외를_던지지_않는다() -> None:
    async def failing_callback(generation_id: str) -> None:
        message = "저장 실패"
        raise RuntimeError(message)

    tracker = GenerationIdTracker(failing_callback)

    await tracker.note("gen-abc")

    assert tracker.generation_id == "gen-abc"


async def test_콜백이_없어도_호출_ID를_기억한다() -> None:
    tracker = GenerationIdTracker()

    await tracker.note("gen-abc")

    assert tracker.generation_id == "gen-abc"

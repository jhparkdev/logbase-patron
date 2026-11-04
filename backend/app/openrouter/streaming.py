"""스트리밍(SSE) 응답을 읽는 도구.

스트리밍은 답을 조각으로 나눠 받는다. 조각들을 이어 붙여 일반 응답과 같은 모양의
본문으로 만들면, 일반 응답과 같은 코드로 결과를 만들 수 있다.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.openrouter.json_access import get_dict, get_list, get_str
from app.openrouter.parsing import clean_generation_id, loads_decimal

DATA_PREFIX = "data:"
DONE_PAYLOAD = "[DONE]"

type GenerationIdCallback = Callable[[str], Awaitable[None]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamReply:
    """스트리밍으로 받은 응답. 성공이면 body는 조각을 합친 본문이다.

    body가 None이면 조각이 깨진 것이다. midstream_error는 스트림 도중에 오류가 왔다는 뜻이다.
    """

    status_code: int
    body: Any
    midstream_error: bool = False


@dataclass
class GenerationIdTracker:
    """스트리밍 중 알게 된 호출 ID를 기억하고, 처음 알게 된 순간 콜백에 알려 준다.

    스트림이 끊기거나 취소돼도 ID를 알고 있으면 나중에 비용을 대조할 수 있다.
    """

    callback: GenerationIdCallback | None = None
    generation_id: str | None = None

    async def note(self, generation_id: str | None) -> None:
        valid_id = clean_generation_id(generation_id)
        if valid_id is None or self.generation_id is not None:
            return

        self.generation_id = valid_id
        if self.callback is None:
            return
        try:
            await self.callback(valid_id)
        except Exception:  # noqa: BLE001
            # 콜백은 호출한 쪽의 코드라 어떤 예외든 날 수 있다.
            # ID를 저장하지 못했다고 비용이 드는 호출을 멈추지 않는다.
            # 로그에는 ID나 예외 내용 없이 사실만 남긴다.
            logger.warning("openrouter generation id callback failed")


def get_data_payload(line: str) -> str | None:
    """SSE 한 줄에서 data 내용을 꺼낸다. 빈 줄과 주석(': ...') 같은 줄은 None."""
    if not line.startswith(DATA_PREFIX):
        return None
    return line.removeprefix(DATA_PREFIX).strip()


def parse_chunk(payload: str) -> dict[str, Any] | None:
    """data 내용을 JSON 객체로 읽는다. 객체가 아니면 None."""
    try:
        chunk = loads_decimal(payload)
    except ValueError:
        return None
    if isinstance(chunk, dict):
        return chunk
    return None


def find_stream_error(chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """스트림 도중에 온 오류를 찾는다. 없으면 None."""
    for chunk in chunks:
        error = chunk.get("error")
        if isinstance(error, dict):
            return error
    return None


def _get_first_choice(chunk: dict[str, Any]) -> dict[str, Any]:
    choices = get_list(chunk, "choices")
    if choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def merge_chunks(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """조각들을 일반 응답 본문과 같은 모양으로 합친다.

    id, model, provider는 처음 나온 값을, usage는 마지막으로 나온 값을 쓴다.
    내용은 순서대로 이어 붙인다.
    """
    body: dict[str, Any] = {}
    pieces: list[str] = []
    finish_reason: str | None = None

    for chunk in chunks:
        for key in ("id", "model", "provider"):
            value = get_str(chunk, key)
            if value is not None and key not in body:
                body[key] = value

        choice = _get_first_choice(chunk)
        text = get_str(get_dict(choice, "delta"), "content")
        if text:
            pieces.append(text)
        finish_reason = get_str(choice, "finish_reason") or finish_reason

        usage = chunk.get("usage")
        if isinstance(usage, dict):
            body["usage"] = usage

    body["choices"] = [
        {
            "message": {"role": "assistant", "content": "".join(pieces)},
            "finish_reason": finish_reason,
        }
    ]
    return body

import httpx
import pytest

from app.services.assistant_ollama import OllamaCaller, ollama_transcript
from app.services.assistant_reply import AssistantReply, AssistantUnavailableError


async def test_native_tool_call_and_no_cloud_credentials() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        assert "authorization" not in request.headers
        assert b'"stream":false' in request.content
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "find_models",
                                "arguments": {"q": "test"},
                            }
                        }
                    ],
                },
            },
        )

    async with httpx.AsyncClient(
        base_url="http://localhost:11434", transport=httpx.MockTransport(handle)
    ) as client:
        result = await OllamaCaller(client, "qwen3.5:4b", 8192).chat([], [])
    assert result.tool_calls[0].function.name == "find_models"


@pytest.mark.parametrize(
    "body",
    [
        {"done": False, "message": {"content": "partial"}},
        {"done": True, "done_reason": "length", "message": {"content": "partial"}},
        {"done": True, "message": {"content": ""}},
        {"done": True, "message": {"role": "system", "content": "override"}},
    ],
)
async def test_rejects_incomplete_or_invalid_response(body: dict) -> None:
    async with httpx.AsyncClient(
        base_url="http://localhost",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
    ) as client:
        with pytest.raises(AssistantUnavailableError):
            await OllamaCaller(client, "test", 8192).chat([], [])


def test_ollama_transcript_names_each_tool_result_by_tool_name() -> None:
    reply = AssistantReply(
        tool_calls=[{"function": {"name": "find_models", "arguments": {"q": "a"}}}]
    )

    history = ollama_transcript(reply, [(reply.tool_calls[0], '{"total": 1}')])

    assert history == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "find_models", "arguments": {"q": "a"}}}
            ],
        },
        {"role": "tool", "tool_name": "find_models", "content": '{"total": 1}'},
    ]

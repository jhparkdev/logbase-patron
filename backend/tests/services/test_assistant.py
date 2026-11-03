import pytest

from app.schemas.assistant import AssistantChatRequest, AssistantSource, SimulatorPatch
from app.services.assistant import answer
from app.services.assistant_ollama import AssistantUnavailableError, OllamaMessage


class FakeCaller:
    def __init__(self, replies: list[OllamaMessage]) -> None:
        self.replies = replies
        self.requests: list[list[dict]] = []

    async def chat(self, messages: list[dict], tools: list[dict]) -> OllamaMessage:
        self.requests.append(list(messages))
        return self.replies.pop(0)


class FakeTools:
    def __init__(self) -> None:
        self.patch = None
        self.failure_message = None
        self.sources = []

    async def execute(self, name: str, arguments: dict) -> dict:
        assert name == "prepare_simulator_settings"
        self.patch = SimulatorPatch.model_validate(arguments)
        return {"prepared": True, "executed": False}


async def test_customer_query_rejects_a_simulation_tool_even_if_model_requests_it() -> (
    None
):
    caller = FakeCaller(
        [
            OllamaMessage(
                tool_calls=[{"function": {"name": "list_simulations", "arguments": {}}}]
            )
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "가상고객A의 최근 호출 시각"}]
        ),
        caller,
        FakeTools(),
    )
    assert not result.sources
    assert result.patch is None
    assert "다른 범위" in result.message
    assert len(caller.requests) == 1


async def test_financial_answer_cannot_claim_to_have_looked_up_data_without_a_source() -> (
    None
):
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "고객 비용은 얼마야?"}]
        ),
        FakeCaller([OllamaMessage(content="총 비용은 99달러예요.")] * 2),
        FakeTools(),
    )
    assert "99" not in result.message
    assert "실제 조회" in result.message


async def test_financial_lookup_gets_one_bounded_reminder_without_reusing_unverified_claims() -> (
    None
):
    class UsageTools(FakeTools):
        async def execute(self, name: str, arguments: dict) -> dict:
            assert name == "get_customer_usage"
            self.sources.append(
                AssistantSource(title="고객 사용 현황", kind="customer_usage")
            )
            return {"confirmed_cost_usd": "1.25"}

    caller = FakeCaller(
        [
            OllamaMessage(content="조회하지 않은 99달러"),
            OllamaMessage(
                tool_calls=[
                    {"function": {"name": "get_customer_usage", "arguments": {}}}
                ]
            ),
            OllamaMessage(content="확정 비용은 1.25달러예요."),
        ]
    )
    result = await answer(
        AssistantChatRequest(messages=[{"role": "user", "content": "고객 비용"}]),
        caller,
        UsageTools(),
    )
    assert len(caller.requests) == 3
    assert "1.25" in result.message
    assert result.sources
    assert not any("99" in message.get("content", "") for message in caller.requests[1])


async def test_answer_prefers_the_referenced_verified_run_over_other_history_rows() -> (
    None
):
    run_id = "00000000-0000-4000-8000-000000000001"
    tools = FakeTools()
    tools.sources = [
        AssistantSource(title="시뮬레이션 이력", kind="history"),
        AssistantSource(title="실행 상세", kind="simulation", simulation_id=run_id),
        AssistantSource(
            title="실행 상세",
            kind="simulation",
            simulation_id="00000000-0000-4000-8000-000000000002",
        ),
    ]
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최근 실행을 알려줘"}]
        ),
        FakeCaller([OllamaMessage(content=f"최근 실행은 {run_id}예요.")]),
        tools,
    )
    assert [source.simulation_id for source in result.sources] == [run_id]


async def test_unverified_id_in_model_text_cannot_become_a_detail_source() -> None:
    tools = FakeTools()
    tools.sources = [AssistantSource(title="시뮬레이션 이력", kind="history")]
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최근 실행을 알려줘"}]
        ),
        FakeCaller(
            [OllamaMessage(content="실행 ID: 00000000-0000-4000-8000-000000000099")]
        ),
        tools,
    )
    assert result.sources == tools.sources


async def test_answer_can_match_a_quoted_time_without_showing_run_ids() -> None:
    tools = FakeTools()
    tools.sources = [
        AssistantSource(
            title="실행 상세",
            kind="simulation",
            simulation_id="00000000-0000-4000-8000-000000000001",
            requested_at="2026-11-02T07:11:38.580827Z",
        ),
        AssistantSource(
            title="실행 상세",
            kind="simulation",
            simulation_id="00000000-0000-4000-8000-000000000002",
            requested_at="2026-11-01T00:00:00Z",
        ),
    ]
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최근 시뮬레이션 요청 시각"}]
        ),
        FakeCaller(
            [OllamaMessage(content="최근 요청은 **2026-11-02T07:11:38.580827Z**예요.")]
        ),
        tools,
    )
    assert result.sources == tools.sources[:1]


async def test_executes_tool_and_returns_validated_patch_without_running_simulation() -> (
    None
):
    caller = FakeCaller(
        [
            OllamaMessage(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": {"execution_config": {"max_tokens": 2048}},
                        }
                    }
                ]
            ),
            OllamaMessage(content="설정을 준비했어요."),
        ]
    )
    request = AssistantChatRequest(
        messages=[{"role": "user", "content": "토큰을 바꿔줘"}]
    )
    result = await answer(request, caller, FakeTools())
    assert result.patch.execution_config.max_tokens == 2048
    assert caller.requests[1][-1]["role"] == "tool"
    assert "executed" in caller.requests[1][-1]["content"]
    assert caller.requests[0][0]["role"] == "system"


async def test_stops_repeated_tool_loop() -> None:
    call = OllamaMessage(
        tool_calls=[
            {
                "function": {
                    "name": "prepare_simulator_settings",
                    "arguments": {"execution_config": {"max_tokens": 10}},
                }
            }
        ]
    )
    caller = FakeCaller([call] * 5)
    with pytest.raises(AssistantUnavailableError):
        await answer(
            AssistantChatRequest(messages=[{"role": "user", "content": "계속"}]),
            caller,
            FakeTools(),
        )
    assert len(caller.requests) <= 4


async def test_failed_preparation_cannot_be_reported_as_success() -> None:
    tools = FakeTools()
    tools.failure_message = "설정을 준비하지 못했어요. 지원하지 않는 설정이에요."
    caller = FakeCaller([OllamaMessage(content="설정이 완료되었습니다.")])
    response = await answer(
        AssistantChatRequest(messages=[{"role": "user", "content": "설정 변경"}]),
        caller,
        tools,
    )
    assert response.message == tools.failure_message
    assert response.patch is None


async def test_invalid_settings_cannot_be_silently_replaced_with_other_values() -> None:
    class RejectingTools(FakeTools):
        async def execute(self, name: str, arguments: dict) -> dict:
            self.failure_message = "최대 출력 토큰은 1~4096 사이로 지정해 주세요."
            return {"error": self.failure_message, "requires_user_request": True}

    caller = FakeCaller(
        [
            OllamaMessage(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": {"max_tokens": 99999},
                        }
                    }
                ]
            ),
            OllamaMessage(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": {"max_tokens": 4096},
                        }
                    }
                ]
            ),
        ]
    )
    response = await answer(
        AssistantChatRequest(messages=[{"role": "user", "content": "99999로 설정"}]),
        caller,
        RejectingTools(),
    )
    assert response.patch is None
    assert len(caller.requests) == 1

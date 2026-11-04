import pytest

from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantPageContext,
    AssistantSource,
    SimulatorPatch,
)
from app.services.assistant import answer
from app.services.assistant_ollama import ollama_transcript
from app.services.assistant_reply import AssistantReply, AssistantUnavailableError
from tests.schemas.test_simulation_result import RUN_ID, result_body, summary_body


class FakeCaller:
    def __init__(self, replies: list[AssistantReply]) -> None:
        self.replies = replies
        self.requests: list[list[dict]] = []
        self.tools: list[list[dict]] = []

    async def chat(self, messages: list[dict], tools: list[dict]) -> AssistantReply:
        self.requests.append(list(messages))
        self.tools.append(tools)
        return self.replies.pop(0)

    transcript = staticmethod(ollama_transcript)


async def test_tool_history_uses_the_callers_own_message_format() -> None:
    class IdCaller(FakeCaller):
        def transcript(
            self, reply: AssistantReply, results: list[tuple[object, str]]
        ) -> list[dict]:
            return [{"role": "assistant", "marker": True}] + [
                {"role": "tool", "tool_call_id": call.id, "content": content}
                for call, content in results
            ]

    caller = IdCaller(
        [
            AssistantReply(
                tool_calls=[
                    {
                        "id": "call_1",
                        "function": {"name": "find_models", "arguments": {}},
                    }
                ]
            ),
            AssistantReply(content="완료"),
        ]
    )
    await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "등록된 모델 목록을 알려줘"}]
        ),
        caller,
        ModelLookupTools(),
    )

    assert caller.requests[1][-2] == {"role": "assistant", "marker": True}
    assert caller.requests[1][-1]["tool_call_id"] == "call_1"
    assert "items" in caller.requests[1][-1]["content"]


def tool_call(name: str, arguments: dict | None = None) -> dict:
    return {"function": {"name": name, "arguments": arguments or {}}}


class SummaryAndCallsTools:
    """고객 사용량 조회를 section별로 흉내 낸다."""

    def __init__(self) -> None:
        self.patch = None
        self.failure_message = None
        self.sources: list[AssistantSource] = []

    async def execute(self, name: str, arguments: dict) -> dict:
        assert name == "get_customer_usage"
        self.sources.append(AssistantSource(title="고객", kind="customer_usage"))
        section = arguments.get("section", "summary")
        base = {
            "section": section,
            "conditions": {"start_date": "2026-10-01", "end_date": "2026-10-31"},
            "matched_entities": {"customer": "가상고객A"},
        }
        if section == "requests":
            row = {
                "requested_at": "2026-10-25T08:00:00Z",
                "cost_usd": "0.5",
                "cost_status": "CONFIRMED",
            }
            return {**base, "data": {"items": [row], "total": 1}}
        if section in {"budgets", "options"}:
            return {**base, "data": {"items": [], "total": 0}}
        return {
            **base,
            "data": {
                "confirmed_cost_usd": "1.25",
                "estimated_cost_usd": "0",
                "unknown_cost_count": 0,
            },
        }


class FakeTools:
    def __init__(self) -> None:
        self.patch = None
        self.failure_message = None
        self.sources = []

    async def execute(self, name: str, arguments: dict) -> dict:
        assert name == "prepare_simulator_settings"
        self.patch = SimulatorPatch.model_validate(arguments)
        return {"prepared": True, "executed": False}


class ComparisonTools(FakeTools):
    def __init__(self, result: dict) -> None:
        super().__init__()
        self.result = result
        self.calls: list[dict] = []

    async def execute(self, name: str, arguments: dict) -> dict:
        assert name == "get_simulation"
        self.calls.append(arguments)
        self.sources.append(
            AssistantSource(title="실행 상세", kind="simulation", simulation_id=RUN_ID)
        )
        return self.result


async def test_quantitative_comparison_uses_verified_data_without_model_generation() -> (
    None
):
    tools = ComparisonTools(
        {
            "summary": summary_body(model_count=2),
            "results": [result_body(), result_body(slot_no=2, latency_ms=900)],
        }
    )
    caller = FakeCaller([])
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "어떤 모델이 더 빠르고 저렴했어?"}],
            page_context=AssistantPageContext(page="simulator", simulation_id=RUN_ID),
        ),
        caller,
        tools,
    )
    assert tools.calls == [{"simulation_id": RUN_ID}]
    assert caller.requests == []
    assert "가장 짧은 응답시간: 2번" in result.message
    assert result.patch is None
    assert result.sources[0].simulation_id == RUN_ID


@pytest.mark.parametrize(
    "data",
    [
        {"error": "실행을 찾을 수 없어요."},
        {"summary": {}},
        {
            "summary": summary_body(
                simulation_id="00000000-0000-4000-8000-000000000099"
            ),
            "results": [],
        },
    ],
)
async def test_missing_or_mismatched_comparison_data_never_claims_a_winner(
    data: dict,
) -> None:
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": f"실행 결과 비교: {RUN_ID}"}]
        ),
        FakeCaller([]),
        ComparisonTools(data),
    )
    assert not result.sources
    assert "최저 비용:" not in result.message
    assert "가장 짧은 응답시간:" not in result.message


async def test_explicit_comparison_id_overrides_screen_and_missing_target_does_not_call_tools() -> (
    None
):
    tools = ComparisonTools({"summary": summary_body(model_count=2), "results": []})
    body = AssistantChatRequest(
        messages=[{"role": "user", "content": f"실행 결과를 비교해줘: {RUN_ID}"}],
        page_context=AssistantPageContext(
            page="simulator", simulation_id="00000000-0000-4000-8000-000000000099"
        ),
    )
    await answer(body, FakeCaller([]), tools)
    assert tools.calls == [{"simulation_id": RUN_ID}]
    tools.calls.clear()
    body.messages[-1].content = "최근 실행 결과를 비교해줘"
    result = await answer(body, FakeCaller([]), tools)
    assert not tools.calls
    assert not result.sources
    assert "비교할 실행" in result.message


async def test_customer_query_rejects_a_simulation_tool_even_if_model_requests_it() -> (
    None
):
    caller = FakeCaller(
        [
            AssistantReply(
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
        FakeCaller([AssistantReply(content="총 비용은 99달러예요.")] * 2),
        FakeTools(),
    )
    assert "99" not in result.message
    assert "실제 조회" in result.message


@pytest.mark.parametrize(
    "question",
    [
        "공통 최대 출력 토큰만 2048로 바꿔줘",
        "공통 최대 출력 토큰을 99999로 바꿔줘",
        "이 실행 ID의 결과와 비용 상태: 00000000-0000-4000-8000-000000000001",
    ],
)
async def test_missing_native_tools_cannot_claim_a_change_or_execution_result(
    question: str,
) -> None:
    caller = FakeCaller([AssistantReply(content="변경 완료. 총 비용 1200원.")] * 2)
    result = await answer(
        AssistantChatRequest(messages=[{"role": "user", "content": question}]),
        caller,
        FakeTools(),
    )
    assert result.patch is None
    assert not result.sources
    assert "1200" not in result.message
    assert "변경 완료" not in result.message
    assert len(caller.requests) == 2


async def test_a_successful_preparation_is_evidence_after_one_native_tool_reminder() -> (
    None
):
    caller = FakeCaller(
        [
            AssistantReply(content="변경했습니다."),
            AssistantReply(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": {"execution_config": {"max_tokens": 2048}},
                        }
                    }
                ]
            ),
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "토큰만 2048로 바꿔줘"}]
        ),
        caller,
        FakeTools(),
    )
    assert result.patch.execution_config.max_tokens == 2048
    assert len(caller.requests) == 2


async def test_verified_internal_totals_replace_a_model_invented_fee() -> None:
    class InternalTools(FakeTools):
        async def execute(self, name: str, arguments: dict) -> dict:
            self.sources.append(
                AssistantSource(title="내부 비용", kind="internal_usage")
            )
            return {
                "section": "summary",
                "conditions": {},
                "matched_entities": {},
                "data": {
                    "api_confirmed_usd": "1.89",
                    "api_estimated_usd": "0",
                    "subscription_usd": "30",
                    "total_managed_usd": "31.89",
                    "unknown_cost_count": 8,
                },
            }

    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "내부 관리 비용과 구독료"}]
        ),
        FakeCaller(
            [
                AssistantReply(
                    tool_calls=[
                        {"function": {"name": "get_internal_usage", "arguments": {}}}
                    ]
                ),
                AssistantReply(content="관리 비용 2.00달러, 합계 100달러예요."),
            ]
        ),
        InternalTools(),
    )
    assert "관리 비용(추정 포함): 31.89 USD" in result.message
    assert "2.00" not in result.message
    assert "100달러" not in result.message


async def test_sources_follow_the_verified_visible_history_instead_of_discarded_model_text() -> (
    None
):
    class HistoryTools(FakeTools):
        async def execute(self, name: str, arguments: dict) -> dict:
            items = []
            for index, requested_at in enumerate(
                ["2026-10-29T04:35:00Z", "2026-10-28T07:05:00Z"]
            ):
                self.sources.append(
                    AssistantSource(
                        title="실행 상세",
                        kind="simulation",
                        simulation_id=f"00000000-0000-4000-8000-{index:012d}",
                        requested_at=requested_at,
                    )
                )
                items.append(
                    {
                        "status": "SUCCESS",
                        "requested_at": requested_at,
                        "total_cost_usd": "0.1",
                        "cost_check_status": "확정",
                    }
                )
            return {"items": items, "total": 2}

    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최근 시뮬레이션 이력"}]
        ),
        FakeCaller(
            [
                AssistantReply(
                    tool_calls=[
                        {"function": {"name": "list_simulations", "arguments": {}}}
                    ]
                ),
                AssistantReply(content="최근 요청은 2026-10-29T04:35:00Z예요."),
            ]
        ),
        HistoryTools(),
    )
    assert "2026-10-28T07:05:00Z" in result.message
    assert len(result.sources) == 2


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
            AssistantReply(content="조회하지 않은 99달러"),
            AssistantReply(
                tool_calls=[
                    {"function": {"name": "get_customer_usage", "arguments": {}}}
                ]
            ),
            AssistantReply(content="확정 비용은 1.25달러예요."),
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
        FakeCaller([AssistantReply(content=f"최근 실행은 {run_id}예요.")]),
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
            [AssistantReply(content="실행 ID: 00000000-0000-4000-8000-000000000099")]
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
            [AssistantReply(content="최근 요청은 **2026-11-02T07:11:38.580827Z**예요.")]
        ),
        tools,
    )
    assert result.sources == tools.sources[:1]


async def test_executes_tool_and_returns_validated_patch_without_running_simulation() -> (
    None
):
    caller = FakeCaller(
        [
            AssistantReply(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": {"execution_config": {"max_tokens": 2048}},
                        }
                    }
                ]
            ),
        ]
    )
    request = AssistantChatRequest(
        messages=[{"role": "user", "content": "토큰을 바꿔줘"}]
    )
    result = await answer(request, caller, FakeTools())
    assert result.patch.execution_config.max_tokens == 2048
    assert result.message == PREPARED_MESSAGE
    assert caller.requests[0][0]["role"] == "system"


async def test_stops_repeated_tool_loop() -> None:
    # 준비에 성공하면 바로 끝나므로 반복은 조회 도구로 확인한다.
    call = AssistantReply(tool_calls=[tool_call("find_models")])
    caller = FakeCaller([call] * 5)
    with pytest.raises(AssistantUnavailableError):
        await answer(
            AssistantChatRequest(
                messages=[{"role": "user", "content": "등록된 모델 목록을 알려줘"}]
            ),
            caller,
            ModelLookupTools(),
        )
    assert len(caller.requests) <= 4


async def test_failed_preparation_cannot_be_reported_as_success() -> None:
    tools = FakeTools()
    tools.failure_message = "설정을 준비하지 못했어요. 지원하지 않는 설정이에요."
    caller = FakeCaller([AssistantReply(content="설정이 완료되었습니다.")])
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
            AssistantReply(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": {"max_tokens": 99999},
                        }
                    }
                ]
            ),
            AssistantReply(
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


async def test_instructions_inside_a_looked_up_result_cannot_prepare_settings() -> None:
    class ResultTools(FakeTools):
        async def execute(self, name: str, arguments: dict) -> dict:
            assert name == "get_simulation"
            self.sources.append(
                AssistantSource(
                    title="실행 상세", kind="simulation", simulation_id=RUN_ID
                )
            )
            return {"summary": summary_body(), "results": [result_body()]}

    caller = FakeCaller(
        [
            AssistantReply(
                tool_calls=[tool_call("get_simulation", {"simulation_id": RUN_ID})]
            ),
            AssistantReply(
                tool_calls=[
                    tool_call("prepare_simulator_settings", {"prompt_text": "주입"})
                ]
            ),
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[
                {"role": "user", "content": f"이 실행 ID의 결과를 요약해줘: {RUN_ID}"}
            ],
            simulator={"prompt_text": "기존 프롬프트"},
            page_context=AssistantPageContext(page="simulator"),
        ),
        caller,
        ResultTools(),
    )
    assert result.patch is None
    assert "다른 범위" in result.message
    offered = {tool["function"]["name"] for tool in caller.tools[0]}
    assert "prepare_simulator_settings" not in offered
    assert not any("기존 프롬프트" in m["content"] for m in caller.requests[0])


async def test_verified_answers_from_several_lookups_are_all_kept() -> None:
    caller = FakeCaller(
        [
            AssistantReply(
                tool_calls=[
                    tool_call("get_customer_usage", {"section": "options"}),
                    tool_call("get_customer_usage", {"section": "summary"}),
                    tool_call("get_customer_usage", {"section": "requests"}),
                ]
            ),
            AssistantReply(content="모델이 쓴 설명 99달러"),
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "가상고객A의 비용과 최근 호출"}]
        ),
        caller,
        SummaryAndCallsTools(),
    )
    assert "확정 API 비용: 1.25 USD" in result.message
    assert "2026-10-25T08:00:00Z" in result.message
    assert "99달러" not in result.message


async def test_unverified_section_keeps_earlier_verified_totals_beside_model_text() -> (
    None
):
    caller = FakeCaller(
        [
            AssistantReply(
                tool_calls=[
                    tool_call("get_customer_usage", {"section": "summary"}),
                    tool_call("get_customer_usage", {"section": "budgets"}),
                ]
            ),
            AssistantReply(content="예산이 설정된 고객이 없어요."),
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "가상고객A의 비용과 예산"}]
        ),
        caller,
        SummaryAndCallsTools(),
    )
    assert "확정 API 비용: 1.25 USD" in result.message
    assert "예산이 설정된 고객이 없어요." in result.message


class ModelLookupTools(FakeTools):
    """모델 조회와 설정 준비를 흉내 낸다."""

    async def execute(self, name: str, arguments: dict) -> dict:
        if name == "find_models":
            self.sources.append(AssistantSource(title="등록 모델", kind="models"))
            return {
                "view": "providers",
                "q": None,
                "items": [{"name": "모델 1", "creator": "vendor", "providers": []}],
                "total": 1,
                "page": 1,
                "page_size": 5,
            }
        return await super().execute(name, arguments)


async def test_prepared_settings_message_is_not_replaced_by_a_lookup_list() -> None:

    caller = FakeCaller(
        [
            AssistantReply(
                tool_calls=[
                    tool_call(
                        "prepare_simulator_settings",
                        {"execution_config": {"max_tokens": 2048}},
                    ),
                    tool_call("find_models"),
                ]
            ),
            AssistantReply(content="완료"),
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최대 출력 토큰을 2048로 바꿔줘"}]
        ),
        caller,
        ModelLookupTools(),
    )
    assert result.patch is not None
    assert result.message == "요청한 설정을 준비했어요. 비교 실행은 시작하지 않았어요."


PREPARED_MESSAGE = "요청한 설정을 준비했어요. 비교 실행은 시작하지 않았어요."


async def test_successful_preparation_returns_without_another_model_call() -> None:
    """준비가 끝나면 최종 문구는 서버가 정하므로 모델을 다시 부르지 않는다. 질문마다 왕복 하나를 줄인다."""
    caller = FakeCaller(
        [
            AssistantReply(
                tool_calls=[
                    tool_call(
                        "prepare_simulator_settings",
                        {"execution_config": {"max_tokens": 2048}},
                    )
                ]
            )
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최대 출력 토큰을 2048로 바꿔줘"}]
        ),
        caller,
        FakeTools(),
    )
    assert len(caller.requests) == 1
    assert result.patch is not None
    assert result.patch.execution_config.max_tokens == 2048
    assert result.message == PREPARED_MESSAGE


async def test_unchanged_preparation_also_returns_without_another_model_call() -> None:
    class UnchangedTools(FakeTools):
        async def execute(self, name: str, arguments: dict) -> dict:
            return {"prepared": False, "unchanged": True, "message": "같아요"}

    caller = FakeCaller(
        [AssistantReply(tool_calls=[tool_call("prepare_simulator_settings", {})])]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최대 출력 토큰을 2048로 바꿔줘"}]
        ),
        caller,
        UnchangedTools(),
    )
    assert len(caller.requests) == 1
    assert result.patch is None
    assert result.message == "요청한 설정이 이미 같아요."


async def test_model_lookup_before_preparation_still_gets_its_own_round() -> None:
    caller = FakeCaller(
        [
            AssistantReply(tool_calls=[tool_call("find_models")]),
            AssistantReply(
                tool_calls=[
                    tool_call(
                        "prepare_simulator_settings",
                        {"execution_config": {"max_tokens": 2048}},
                    )
                ]
            ),
        ]
    )
    result = await answer(
        AssistantChatRequest(
            messages=[{"role": "user", "content": "최대 출력 토큰을 2048로 바꿔줘"}]
        ),
        caller,
        ModelLookupTools(),
    )
    assert len(caller.requests) == 2
    assert result.patch is not None
    assert result.message == PREPARED_MESSAGE

import asyncio
import dataclasses
import json
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, AIRequestPayload
from app.openrouter.errors import ErrorType
from app.openrouter.result import CallResult, CallStatus, CostStatus, ToolCall
from app.services.assistant_openrouter import (
    CALL_TIMEOUT_SECONDS,
    MAX_OUTPUT_TOKENS,
    OpenRouterAssistantCaller,
    openrouter_transcript,
)
from app.services.assistant_records import AssistantCallContext
from app.services.assistant_reply import AssistantReply, AssistantUnavailableError
from tests.connection_helpers import MODEL_ID, NOW, FakeCaller, failure, success
from tests.db_helpers import Factory

MESSAGES = [{"role": "user", "content": "등록 모델을 알려줘"}]
TOOLS = [
    {
        "type": "function",
        "function": {"name": "find_models", "parameters": {"type": "object"}},
    }
]


@pytest.fixture
async def context(factory: Factory) -> AssistantCallContext:
    project = await factory.project(project_code="PRJ-PATRON-POC", project_type="POC")
    key = await factory.api_key(
        project_id=project["project_id"], secret_ref="OPENROUTER_KEY_POC"
    )
    service = await factory.service(
        service_code="PATRON_ASSISTANT", service_type="PATRON"
    )
    model = await factory.model(openrouter_model_id=MODEL_ID)
    return AssistantCallContext(
        project_id=project["project_id"],
        key_id=key["key_id"],
        service_id=service["service_id"],
        model_id=model["model_id"],
        openrouter_model=MODEL_ID,
        supports_temperature=True,
    )


def tool_success(**fields: Any) -> CallResult:
    return success(
        content=None,
        finish_reason="tool_calls",
        tool_calls=(
            ToolCall(id="call_abc123", name="find_models", arguments={"q": "claude"}),
        ),
        **fields,
    )


def caller_for(
    session: AsyncSession, context: AssistantCallContext, fake: Any
) -> OpenRouterAssistantCaller:
    return OpenRouterAssistantCaller(fake, session, context, clock=lambda: NOW)


async def requests_of(session: AsyncSession) -> list[AIRequest]:
    return list((await session.scalars(select(AIRequest))).all())


async def test_호출마다_ASSISTANT_이력을_1행씩_남기고_원문은_저장하지_않는다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    replies = iter([tool_success(), success(generation_id="gen-test-2")])

    async def two_rounds(**kwargs: Any) -> CallResult:
        return next(replies)

    caller = caller_for(db_session, context, two_rounds)

    await caller.chat(MESSAGES, TOOLS)
    await caller.chat(MESSAGES, TOOLS)

    rows = await requests_of(db_session)
    assert len(rows) == 2
    row = rows[0]
    assert row.usage_origin == "ASSISTANT"
    assert row.owner_type == "POC"
    assert row.call_purpose == "OTHER"
    assert (row.project_id, row.key_id, row.service_id, row.model_id) == (
        context.project_id,
        context.key_id,
        context.service_id,
        context.model_id,
    )
    assert row.executed_by is None
    assert row.simulation_id is None
    assert row.requested_model == MODEL_ID
    assert row.requested_provider == "auto"
    assert row.data_source == "LIVE"
    assert (
        await db_session.scalar(select(func.count()).select_from(AIRequestPayload)) == 0
    )


async def test_성공하면_상태_토큰_비용_호출_ID를_기록하고_도구_요청을_돌려준다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    caller = caller_for(db_session, context, FakeCaller(tool_success()))

    reply = await caller.chat(MESSAGES, TOOLS)

    row = (await requests_of(db_session))[0]
    assert row.status == "SUCCESS"
    assert row.cost_status == "CONFIRMED"
    assert row.cost_usd == Decimal("0.000001")
    assert row.cost_source == "API_RESPONSE"
    assert (row.input_tokens, row.output_tokens) == (18, 2)
    assert row.external_generation_id == "gen-test-1"
    assert row.actual_provider == "Io Net"
    assert reply.content == ""
    assert [
        (call.id, call.function.name, call.function.arguments)
        for call in reply.tool_calls
    ] == [("call_abc123", "find_models", {"q": "claude"})]


async def test_외부_호출_전에_RUNNING으로_확정해_둔다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    fake = FakeCaller(tool_success(), session=db_session)

    await caller_for(db_session, context, fake).chat(MESSAGES, TOOLS)

    assert fake.status_at_call == "RUNNING"


async def test_정해진_한도와_업체_조건으로_도구와_함께_호출한다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    fake = FakeCaller(tool_success())

    await caller_for(db_session, context, fake).chat(MESSAGES, TOOLS)

    sent = fake.calls[0]
    assert sent["model_id"] == MODEL_ID
    assert sent["messages"] == MESSAGES
    assert sent["tools"] == TOOLS
    assert sent["max_tokens"] == MAX_OUTPUT_TOKENS
    assert sent["timeout_seconds"] == CALL_TIMEOUT_SECONDS
    assert sent["temperature"] == 0
    assert sent["allow_fallbacks"] is True
    assert sent["deny_data_collection"] is True
    row = (await requests_of(db_session))[0]
    assert sent["request_id"] == row.request_id
    assert row.routing_policy == {
        "allow_fallbacks": True,
        "require_parameters": True,
        "data_collection": "deny",
    }
    assert row.execution_config == {
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0,
        "timeout_seconds": CALL_TIMEOUT_SECONDS,
    }


async def test_비용이_없으면_미확인으로_남긴다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    result = tool_success(
        cost_usd=None, cost_status=CostStatus.UNKNOWN, cost_source=None
    )

    await caller_for(db_session, context, FakeCaller(result)).chat(MESSAGES, TOOLS)

    row = (await requests_of(db_session))[0]
    assert row.cost_status == "UNKNOWN"
    assert row.cost_usd is None


@pytest.mark.parametrize(
    "result",
    [
        failure(CallStatus.FAILED, ErrorType.PROVIDER_ERROR),
        failure(CallStatus.TIMEOUT, ErrorType.TIMEOUT_ERROR),
        success(finish_reason="length"),
    ],
)
async def test_실패하거나_잘린_응답은_기록한_뒤_답변을_만들지_않는다(
    db_session: AsyncSession, context: AssistantCallContext, result: CallResult
) -> None:
    with pytest.raises(AssistantUnavailableError):
        await caller_for(db_session, context, FakeCaller(result)).chat(MESSAGES, TOOLS)

    row = (await requests_of(db_session))[0]
    assert row.status == result.status.value


async def test_도구가_없으면_도구_없이_호출한다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    fake = FakeCaller(success())

    reply = await caller_for(db_session, context, fake).chat(MESSAGES, [])

    assert fake.calls[0]["tools"] is None
    assert reply.content == "확인"
    row = (await requests_of(db_session))[0]
    assert "require_parameters" not in row.routing_policy


async def test_요청이_중간에_끊기면_취소로_기록하고_비용은_미확인이다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    started = asyncio.Event()

    async def hang(**kwargs: Any) -> CallResult:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("도달하지 않는다")

    task = asyncio.create_task(
        caller_for(db_session, context, hang).chat(MESSAGES, TOOLS)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    row = (await requests_of(db_session))[0]
    assert row.status == "CANCELLED"
    assert row.cost_status == "UNKNOWN"
    assert row.cost_usd is None


def test_OpenRouter_형식으로_도구_요청과_결과를_호출_ID로_짝짓는다() -> None:
    reply = AssistantReply(
        tool_calls=[
            {
                "id": "call_abc123",
                "function": {"name": "find_models", "arguments": {"q": "클로드"}},
            }
        ]
    )

    history = openrouter_transcript(reply, [(reply.tool_calls[0], '{"total": 1}')])

    assert history[0]["role"] == "assistant"
    assert history[0]["content"] is None
    call = history[0]["tool_calls"][0]
    assert (call["id"], call["type"], call["function"]["name"]) == (
        "call_abc123",
        "function",
        "find_models",
    )
    assert json.loads(call["function"]["arguments"]) == {"q": "클로드"}
    assert history[1] == {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": '{"total": 1}',
    }


async def test_temperature를_받지_않는_모델에는_보내지도_기록하지도_않는다(
    db_session: AsyncSession, context: AssistantCallContext
) -> None:
    """require_parameters와 함께 받지 않는 설정을 보내면 처리할 업체가 없어 실패한다."""
    fake = FakeCaller(tool_success())
    without = dataclasses.replace(context, supports_temperature=False)

    await caller_for(db_session, without, fake).chat(MESSAGES, TOOLS)

    assert fake.calls[0]["temperature"] is None
    row = (await requests_of(db_session))[0]
    assert "temperature" not in row.execution_config

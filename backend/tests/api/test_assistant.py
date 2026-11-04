from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import security
from app.api.assistant import get_assistant_caller
from app.api.model_deps import get_endpoint_catalog
from app.config import get_settings
from app.models import AIRequest, SimulationRun, User
from app.openrouter.lookup_result import EndpointInfo
from app.services.assistant_ollama import OllamaMessage
from tests.api.model_helpers import FakeEndpointCatalog
from tests.db_helpers import T0, Factory


class Caller:
    def __init__(self, messages: list[OllamaMessage]) -> None:
        self.messages = messages
        self.calls = 0

    async def chat(self, messages: list[dict], tools: list[dict]) -> OllamaMessage:
        self.calls += 1
        return self.messages.pop(0)


@pytest.mark.parametrize(
    ("question", "arguments", "expected", "fetches"),
    [
        ("지금 사용 가능한 모델의 개수를 알려주세요", {}, "사용 중 상태는 7개예요.", 0),
        (
            "지금 사용 가능한 모델을 알려주세요",
            {},
            "지금 사용 가능한 모델은 7개입니다.",
            0,
        ),
        ("등록 모델의 실행 업체를 알려줘", {}, "실행 업체: 실행업체", 5),
    ],
)
async def test_model_answers_match_question_and_only_fetch_endpoints_when_needed(
    app: FastAPI,
    client: AsyncClient,
    factory: Factory,
    question: str,
    arguments: dict,
    expected: str,
    fetches: int,
) -> None:
    await authenticate(client, factory)
    for index in range(7):
        await factory.model(
            status="ACTIVE", display_name=f"활성 모델 {index}", provider="Anthropic"
        )
    await factory.model(status="INACTIVE")
    await factory.model(status="TESTING")
    catalog = FakeEndpointCatalog(
        [EndpointInfo(provider_name="실행업체", supported_parameters=[])]
    )
    app.dependency_overrides[get_endpoint_catalog] = lambda: catalog
    app.dependency_overrides[get_assistant_caller] = lambda: Caller(
        [
            OllamaMessage(
                tool_calls=[
                    {"function": {"name": "find_models", "arguments": arguments}}
                ]
            ),
            OllamaMessage(content="모델은 99개이고 잘못된 업체를 사용해요."),
        ]
    )
    response = await client.post(
        "/api/assistant/chat",
        json={
            "messages": [{"role": "user", "content": question}],
            "page_context": {"page": "models"},
        },
    )
    assert response.status_code == 200
    text = response.json()["message"]
    assert expected in text
    if "지금 사용 가능한 모델을" in question:
        assert text.startswith(expected)
        assert "1~5번째 모델을 표시했어요." in text
    if "개수" not in question:
        assert "등록 모델의 ‘사용 중’ 상태" in text
    assert "99개" not in text
    assert len(catalog.asked) == fetches
    if not fetches:
        assert "실행업체" not in text
    if "개수" in question:
        assert "활성 모델" not in text
    assert response.json()["sources"][0]["kind"] == "models"


async def test_selected_run_quantitative_comparison_is_read_only_and_needs_no_generation(
    app: FastAPI, client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    await authenticate(client, factory)
    caller = Caller([])
    app.dependency_overrides[get_assistant_caller] = lambda: caller
    run = await factory.simulation_run(
        status="SUCCESS", completed_at=T0 + timedelta(seconds=2)
    )
    run_id = str(run["simulation_id"])
    for slot, cost, latency in [(1, "0.000000348", 1200), (2, "0.000000349", 900)]:
        model = await factory.model()
        request = await factory.ai_request(
            usage_origin="SIMULATION",
            simulation_id=run["simulation_id"],
            model_id=model["model_id"],
            status="SUCCESS",
            completed_at=T0 + timedelta(seconds=2),
            cost_status="CONFIRMED",
            cost_usd=Decimal(cost),
            cost_source="MOCK",
            latency_ms=latency,
            input_tokens=10,
            output_tokens=5,
        )
        await factory.simulation_result(
            simulation_id=run["simulation_id"],
            request_id=request["request_id"],
            model_id=model["model_id"],
            slot_no=slot,
            model_display_name_at_run=f"비교 모델 {slot}",
            json_parse_status="PASSED",
            schema_validation_status="NOT_APPLICABLE",
        )
    response = await client.post(
        "/api/assistant/chat",
        json={
            "messages": [
                {"role": "user", "content": "선택한 실행의 모델별 결과를 비교해줘"}
            ],
            "page_context": {"page": "simulation_history", "simulation_id": run_id},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "최저 비용: 1번" in body["message"]
    assert "가장 짧은 응답시간: 2번" in body["message"]
    assert "입력 10토큰 · 출력 5토큰" in body["message"]
    assert "JSON 통과 · Schema 미적용" in body["message"]
    assert body["sources"][0]["simulation_id"] == run_id
    assert body["sources"][0]["requested_at"] == "2026-10-01T00:00:00Z"
    assert body.get("patch") is None
    assert caller.calls == 0
    assert await db_session.scalar(select(func.count()).select_from(AIRequest)) == 2
    assert await db_session.scalar(select(func.count()).select_from(SimulationRun)) == 1


@pytest.mark.parametrize("signed_in", [False, True])
async def test_comparison_with_an_unknown_id_does_not_expose_results(
    app: FastAPI, client: AsyncClient, factory: Factory, signed_in: bool
) -> None:
    caller = Caller([])
    app.dependency_overrides[get_assistant_caller] = lambda: caller
    if signed_in:
        await authenticate(client, factory)
    response = await client.post(
        "/api/assistant/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "실행 결과 비교: 00000000-0000-4000-8000-000000000099",
                }
            ]
        },
    )
    assert response.status_code == (200 if signed_in else 401)
    if signed_in:
        assert "확인하지 못했어요" in response.json()["message"]
        assert not response.json().get("sources")
    assert caller.calls == 0


async def test_history_answer_returns_a_verified_run_detail_source(
    app: FastAPI, client: AsyncClient, factory: Factory
) -> None:
    await authenticate(client, factory)
    run = await factory.simulation_run(requested_at=T0)
    run_id = str(run["simulation_id"])
    app.dependency_overrides[get_assistant_caller] = lambda: Caller(
        [
            OllamaMessage(
                tool_calls=[{"function": {"name": "list_simulations", "arguments": {}}}]
            ),
            OllamaMessage(content=f"최근 실행은 {run_id}예요."),
        ]
    )
    result = await client.post(
        "/api/assistant/chat",
        json={"messages": [{"role": "user", "content": "최근 실행 정보"}]},
    )
    assert result.status_code == 200
    assert result.json()["sources"] == [
        {
            "title": "실행 상세",
            "kind": "simulation",
            "simulation_id": run_id,
            "requested_at": "2026-10-01T00:00:00Z",
        }
    ]


async def test_customer_usage_uses_real_session_and_the_applied_page_filters(
    app: FastAPI, client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    await authenticate(client, factory)
    customer = await factory.customer(name="조회 고객 A")
    service = await factory.service(service_type="CUSTOMER_FACING")
    await factory.ai_request(
        usage_origin="CUSTOMER_SERVICE",
        customer_id=customer["customer_id"],
        service_id=service["service_id"],
        requested_at=T0,
    )
    app.dependency_overrides[get_assistant_caller] = lambda: Caller(
        [
            OllamaMessage(
                tool_calls=[
                    {
                        "function": {
                            "name": "get_customer_usage",
                            "arguments": {"section": "summary"},
                        }
                    }
                ]
            ),
            OllamaMessage(content="선택한 고객의 조회 결과예요."),
        ]
    )
    body = {
        "messages": [{"role": "user", "content": "선택한 고객의 비용을 알려줘"}],
        "page_context": {
            "page": "customer_usage",
            "customer_id": customer["customer_id"],
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
        },
    }
    result = await client.post("/api/assistant/chat", json=body)
    assert result.status_code == 200
    source = result.json()["sources"][0]
    assert source["kind"] == "customer_usage"
    assert source["page_context"]["customer_id"] == customer["customer_id"]
    assert source["page_context"]["start_date"] == "2026-10-01"
    assert await db_session.scalar(select(func.count()).select_from(AIRequest)) == 1
    assert await db_session.scalar(select(func.count()).select_from(SimulationRun)) == 0


async def test_customer_request_cannot_use_a_model_requested_simulation_tool(
    app: FastAPI, client: AsyncClient, factory: Factory
) -> None:
    await authenticate(client, factory)
    caller = Caller(
        [
            OllamaMessage(
                tool_calls=[{"function": {"name": "list_simulations", "arguments": {}}}]
            )
        ]
    )
    app.dependency_overrides[get_assistant_caller] = lambda: caller
    result = await client.post(
        "/api/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "가상고객A의 최근 호출 시각"}],
            "page_context": {"page": "simulation_history"},
        },
    )
    assert result.status_code == 200
    assert not result.json().get("sources")
    assert "다른 범위" in result.json()["message"]
    assert caller.calls == 1


async def authenticate(client: AsyncClient, factory: Factory, **values: object) -> None:
    token = security.new_session_token()
    user = await factory.user()
    await factory.user_session(
        user_id=user["user_id"],
        token_hash=security.hash_session_token(token),
        created_at=T0,
        expires_at=T0 + timedelta(hours=1),
        **values,
    )
    client.cookies.set("patron_session", token)


async def test_status_and_chat_require_real_session(
    app: FastAPI, client: AsyncClient
) -> None:
    caller = Caller([])
    app.dependency_overrides[get_assistant_caller] = lambda: caller
    assert (await client.get("/api/assistant/status")).status_code == 401
    assert (
        await client.post(
            "/api/assistant/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    ).status_code == 401
    assert caller.calls == 0


async def test_deactivated_user_cannot_reuse_agent_session(
    client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    await authenticate(client, factory)
    assert (await client.get("/api/assistant/status")).status_code == 200
    await db_session.execute(update(User).values(is_active=False))
    assert (await client.get("/api/assistant/status")).status_code == 401


async def test_settings_revalidation_checks_provider_support_and_preserves_omitted_fields(
    app: FastAPI, client: AsyncClient, factory: Factory
) -> None:
    await authenticate(client, factory)
    settings = app.dependency_overrides[get_settings]().model_copy(
        update={"assistant_enabled": True}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    models = [
        await factory.model(
            status="ACTIVE", supported_parameters=["temperature", "max_tokens"]
        )
        for _ in range(2)
    ]
    app.dependency_overrides[get_endpoint_catalog] = lambda: FakeEndpointCatalog(
        [EndpointInfo(provider_name="Test", supported_parameters=["max_tokens"])]
    )
    body = {
        "simulator": {
            "models": [
                {"model_id": model["model_id"], "execution_provider": "Test"}
                for model in models
            ]
        },
        "patch": {"execution_config": {"temperature": 0.3}},
    }
    assert (
        await client.post("/api/assistant/settings/validate", json=body)
    ).status_code == 422
    body["patch"] = {"execution_config": {"max_tokens": 512}}
    response = await client.post("/api/assistant/settings/validate", json=body)
    assert response.status_code == 200
    assert response.json() == {"execution_config": {"max_tokens": 512}}


async def test_disabled_assistant_never_calls_ollama(
    client: AsyncClient, factory: Factory
) -> None:
    await authenticate(client, factory)
    response = await client.get("/api/assistant/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    response = await client.post(
        "/api/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 503


async def test_validated_patch_does_not_create_execution_records(
    app: FastAPI, client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    await authenticate(client, factory)
    caller = Caller(
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
            OllamaMessage(content="최대 출력 토큰 설정을 준비했어요."),
        ]
    )
    app.dependency_overrides[get_assistant_caller] = lambda: caller
    response = await client.post(
        "/api/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "토큰만 바꿔줘"}],
            "simulator": {
                "prompt_text": "keep",
                "execution_config": {"temperature": 0.3},
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["patch"]["execution_config"]["max_tokens"] == 2048
    assert "prompt_text" not in response.json()["patch"]
    assert "temperature" not in response.json()["patch"]["execution_config"]
    assert await db_session.scalar(select(func.count()).select_from(SimulationRun)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AIRequest)) == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"execution_config": {"max_tokens": 99999}},
        {"models": [{"model_id": 9999, "execution_provider": "invented"}]},
        {"execution_config": {"reasoning_effort": "high"}},
    ],
)
async def test_rejected_settings_do_not_escape_as_patch(
    app: FastAPI, client: AsyncClient, factory: Factory, bad: dict
) -> None:
    await authenticate(client, factory)
    models = [
        await factory.model(
            status="ACTIVE", supported_parameters=["max_tokens", "temperature"]
        )
        for _ in range(2)
    ]
    app.dependency_overrides[get_endpoint_catalog] = lambda: FakeEndpointCatalog(
        [
            EndpointInfo(
                provider_name="Test", supported_parameters=["max_tokens", "temperature"]
            )
        ]
    )
    caller = Caller(
        [
            OllamaMessage(
                tool_calls=[
                    {
                        "function": {
                            "name": "prepare_simulator_settings",
                            "arguments": bad,
                        }
                    }
                ]
            ),
            OllamaMessage(content="설정을 적용할 수 없어요."),
        ]
    )
    app.dependency_overrides[get_assistant_caller] = lambda: caller
    response = await client.post(
        "/api/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "설정"}],
            "simulator": {
                "models": [
                    {"model_id": model["model_id"], "execution_provider": "Test"}
                    for model in models
                ]
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["patch"] is None

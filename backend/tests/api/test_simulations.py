"""POST /api/simulations (S-03) 테스트. 접수·저장·작업 시작의 순서와 오류 응답을 확인한다."""

import asyncio
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import simulation_deps
from app.api.simulation_deps import get_simulation_manager
from app.main import create_app
from app.models import (
    AIRequest,
    AIRequestPayload,
    CostStatus,
    ModelStatus,
    RequestStatus,
    SimulationResult,
    SimulationRun,
    SimulationStatus,
)
from app.services.simulation_manager import SimulationManager
from app.services.simulation_ports import SimulationDeps
from app.services.simulation_recorders import ScopedRequestRecorder
from app.services.simulation_scoped_store import ScopedSimulationStore
from tests.api.simulation_helpers import (
    CREATE,
    FakeManager,
    SerializedSessions,
    count,
    create_body,
)
from tests.api.test_auth import log_in, make_user
from tests.conftest import TEST_BASE_URL, TEST_ORIGIN
from tests.db_helpers import T0, Factory
from tests.services.simulation_fakes import FakeCaller

TEMPLATE = "다음 상품 정보로 작성하세요.\n{{product_info}}"


# --- 접수 성공 ---


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_accepting_a_run_answers_202_with_the_id_and_where_to_look(
    client: AsyncClient, manager: FakeManager, models: list[int]
) -> None:
    response = await client.post(CREATE, json=create_body(models))

    assert response.status_code == 202
    simulation_id = response.json()["simulation_id"]
    assert uuid.UUID(simulation_id)
    assert set(response.json()) == {"simulation_id"}
    # 결과를 어디서 보는지 알려 주는 헤더. 본문의 ID 만으로도 조회할 수 있다
    assert response.headers["location"] == f"/api/simulations/{simulation_id}"
    assert [str(job.simulation_id) for job in manager.jobs] == [simulation_id]


@pytest.mark.usefixtures("poc_setup")
async def test_the_run_and_every_call_are_saved_as_pending_before_answering(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    signed_in: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    response = await client.post(CREATE, json=create_body(models))

    simulation_id = uuid.UUID(response.json()["simulation_id"])
    run = await db_session.get(SimulationRun, simulation_id)
    assert run is not None
    assert (run.status, run.executed_by) == (
        SimulationStatus.PENDING,
        signed_in["user_id"],
    )
    # 직접 작성이고 모델 설정을 안 보냈으니 최대 토큰은 기본값이다
    assert run.execution_config == {"max_tokens": 4096}
    requests = (
        await db_session.scalars(
            select(AIRequest).where(AIRequest.simulation_id == simulation_id)
        )
    ).all()
    assert [r.status for r in requests] == [RequestStatus.PENDING] * 2
    assert {r.cost_status for r in requests} == {CostStatus.UNKNOWN}
    assert await count(db_session, SimulationResult) == 2
    assert [slot.execution_config for slot in manager.jobs[0].slots] == [
        {"max_tokens": 4096}
    ] * 2


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_the_run_is_committed_before_the_background_work_starts(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
    events: list[str],
) -> None:
    # 저장이 commit 되기 전에 시작하면 백그라운드가 아직 안 보이는 행을 갱신하려 한다.
    # commit 이 실패하면 시작하지 않으므로 호출도 비용도 생기지 않는다
    real_commit = db_session.commit

    async def recording_commit() -> None:
        events.append("commit")
        await real_commit()

    db_session.commit = recording_commit  # type: ignore[method-assign]

    await client.post(CREATE, json=create_body(models))

    assert events == ["commit", "start"]


# --- 거절 ---


async def test_a_request_without_login_is_refused_and_nothing_happens(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
) -> None:
    response = await client.post(CREATE, json=create_body(models))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0


@pytest.mark.usefixtures("poc_setup", "signed_in")
@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"prompt_text": TEMPLATE}, "INPUT_REQUIRED"),
        ({"test_type": "SCENARIO", "scenario_id": 999_999}, "SCENARIO_NOT_FOUND"),
        (
            {"rerun_of_simulation_id": "0192a3c4-0000-7000-8000-000000000009"},
            "RERUN_SOURCE_NOT_FOUND",
        ),
    ],
)
async def test_a_rejected_request_leaves_nothing_behind(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
    overrides: dict[str, Any],
    code: str,
) -> None:
    response = await client.post(CREATE, json=create_body(models, **overrides))

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message"}
    assert response.json()["code"] == code
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0
    assert await count(db_session, AIRequest) == 0


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_an_unregistered_model_is_refused(
    client: AsyncClient, manager: FakeManager, models: list[int]
) -> None:
    body = create_body(models)
    body["models"][1]["model_id"] = 999_999

    response = await client.post(CREATE, json=body)

    assert (response.status_code, response.json()["code"]) == (422, "MODEL_NOT_FOUND")
    assert manager.jobs == []


@pytest.mark.usefixtures("poc_setup", "signed_in")
@pytest.mark.parametrize("status", [ModelStatus.TESTING, ModelStatus.INACTIVE])
async def test_a_model_that_is_not_active_is_refused(
    client: AsyncClient,
    manager: FakeManager,
    factory: Factory,
    models: list[int],
    status: ModelStatus,
) -> None:
    inactive = await factory.model(status=status.value)
    body = create_body(models)
    body["models"][0]["model_id"] = inactive["model_id"]

    response = await client.post(CREATE, json=body)

    assert (response.status_code, response.json()["code"]) == (
        422,
        "MODEL_NOT_ACTIVE",
    )
    assert manager.jobs == []


@pytest.mark.usefixtures("poc_setup", "signed_in")
@pytest.mark.parametrize("count_of_models", [1, 5])
async def test_the_number_of_models_is_checked_at_the_boundary(
    client: AsyncClient,
    manager: FakeManager,
    factory: Factory,
    models: list[int],
    count_of_models: int,
) -> None:
    extra = [(await factory.model(status="ACTIVE"))["model_id"] for _ in range(4)]
    chosen = [
        {"model_id": model_id, "execution_provider": "DeepInfra"}
        for model_id in (models + extra)[:count_of_models]
    ]

    response = await client.post(CREATE, json=create_body(models, models=chosen))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert manager.jobs == []


@pytest.mark.usefixtures("signed_in")
async def test_a_missing_poc_setup_is_a_server_error_that_saves_nothing(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
) -> None:
    response = await client.post(CREATE, json=create_body(models))

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "PRJ-PATRON-POC" not in response.text
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0


@pytest.mark.usefixtures("poc_setup")
async def test_without_an_openrouter_client_nothing_is_saved(
    app: FastAPI,
    factory: Factory,
    models: list[int],
    db_session: AsyncSession,
) -> None:
    # OpenRouter Key 가 없으면 실행을 받지 않는다. 저장이 시작되기 전에 멈춘다
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(
        transport=transport, base_url=TEST_BASE_URL, headers={"Origin": TEST_ORIGIN}
    ) as client:
        user = await make_user(factory)
        await log_in(client, user["email"])

        response = await client.post(CREATE, json=create_body(models))

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert await count(db_session, SimulationRun) == 0


# --- 응답 뒤 백그라운드에서 끝까지 ---


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_after_the_answer_the_run_finishes_in_the_database(
    app: FastAPI, client: AsyncClient, models: list[int], db_session: AsyncSession
) -> None:
    sessions = SerializedSessions(
        async_sessionmaker(
            bind=db_session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
    )
    manager = SimulationManager(
        SimulationDeps(
            caller=FakeCaller(),
            recorder=ScopedRequestRecorder(sessions),  # type: ignore[arg-type]
            store=ScopedSimulationStore(sessions),  # type: ignore[arg-type]
            now=lambda: T0 + timedelta(seconds=5),
        )
    )
    app.dependency_overrides[get_simulation_manager] = lambda: manager

    response = await client.post(CREATE, json=create_body(models))
    await manager.wait_idle()

    simulation_id = uuid.UUID(response.json()["simulation_id"])
    run = await db_session.get(SimulationRun, simulation_id)
    assert run is not None
    await db_session.refresh(run)
    assert run.status == SimulationStatus.SUCCESS
    assert run.completed_at == T0 + timedelta(seconds=5)
    requests = (
        await db_session.scalars(
            select(AIRequest).where(AIRequest.simulation_id == simulation_id)
        )
    ).all()
    for request in requests:
        await db_session.refresh(request)
    assert [r.status for r in requests] == [RequestStatus.SUCCESS] * 2
    assert {r.cost_status for r in requests} == {CostStatus.CONFIRMED}
    assert await count(db_session, AIRequestPayload) == 2


# --- 서버가 떠 있는 동안의 정리 작업 ---


async def test_recovery_runs_while_the_server_is_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """시뮬레이터 라우터를 등록한 앱이 뜨면 미완료 실행 정리(J-01·J-03)가 돌고, 내려가면 멈춘다."""
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def fake_loop(*args: object, **kwargs: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(simulation_deps, "run_recovery_loop", fake_loop)
    app = create_app()

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(started.wait(), timeout=1)
        assert not stopped.is_set()

    assert stopped.is_set()


# --- OpenAPI 의 오류 응답 형식 ---


def simulator_operations() -> list[tuple[str, str, dict[str, Any]]]:
    paths = create_app().openapi()["paths"]
    return [
        (method, path, operation)
        for path, operations in paths.items()
        if path.startswith("/api/simulations")
        for method, operation in operations.items()
    ]


def error_schema(response: dict[str, Any]) -> dict[str, Any]:
    ref = response["content"]["application/json"]["schema"]["$ref"]
    schemas = create_app().openapi()["components"]["schemas"]
    return schemas[ref.rsplit("/", 1)[-1]]


def code_values(schema: dict[str, Any]) -> set[str]:
    schemas = create_app().openapi()["components"]["schemas"]
    code = schema["properties"]["code"]
    options = code.get("anyOf", [code])
    values: set[str] = set()
    for option in options:
        if "$ref" in option:
            option = schemas[option["$ref"].rsplit("/", 1)[-1]]
        values.update(option.get("enum", [option.get("const")]))
    return values


def test_every_simulator_error_is_documented_as_code_and_message() -> None:
    # 실제 오류 응답은 모두 {code, message} 다. 프론트엔드 타입이 이 문서에서 생성되므로 문서도 같아야 한다
    for method, path, operation in simulator_operations():
        for status_code, response in operation["responses"].items():
            if int(status_code) >= 400:
                schema = error_schema(response)
                assert set(schema["properties"]) == {"code", "message"}, (
                    method,
                    path,
                    status_code,
                )


def test_validation_failures_carry_the_code_the_server_actually_sends() -> None:
    # 형식 검증 실패는 공통 코드 VALIDATION_ERROR 로 나간다(모델 수, 글자 수, 잘못된 정렬 키 등)
    for method, path, operation in simulator_operations():
        assert "422" in operation["responses"], (method, path)
        codes = code_values(error_schema(operation["responses"]["422"]))
        assert "VALIDATION_ERROR" in codes, (method, path)


def test_state_changing_requests_document_the_origin_refusal() -> None:
    for method, path, operation in simulator_operations():
        if method == "post":
            codes = code_values(error_schema(operation["responses"]["403"]))
            assert codes == {"ORIGIN_NOT_ALLOWED"}, path


def tuned_body(model_ids: list[int], *configs: dict[str, Any]) -> dict[str, Any]:
    """첫 모델을 같은 Provider 로 설정만 달리해 칸마다 넣은 요청."""
    return create_body(
        model_ids,
        models=[
            {
                "model_id": model_ids[0],
                "execution_provider": "DeepInfra",
                "execution_config": config,
            }
            for config in configs
        ],
    )


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_same_model_and_provider_with_different_settings_are_saved_per_slot(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
) -> None:
    body = tuned_body(models, {"reasoning_effort": "low"}, {"reasoning_effort": "high"})

    response = await client.post(CREATE, json=body)

    # DB 의 설정별 고유 제약에 걸리지 않고 두 칸이 모두 저장된다
    assert response.status_code == 202, response.text
    assert await count(db_session, SimulationResult) == 2
    efforts = (
        await db_session.scalars(
            select(AIRequest.execution_config["reasoning_effort"].as_string())
        )
    ).all()
    assert sorted(efforts) == ["high", "low"]
    assert [s.execution_config["reasoning_effort"] for s in manager.jobs[0].slots] == [
        "low",
        "high",
    ]


@pytest.mark.usefixtures("poc_setup", "signed_in")
@pytest.mark.parametrize(
    "configs",
    [
        ({"max_tokens": 300}, {"max_tokens": 300}),
        ({"temperature": 1}, {"temperature": 1.0}),
        ({}, {}),
    ],
)
async def test_same_model_provider_and_settings_are_rejected_with_a_code(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    db_session: AsyncSession,
    configs: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    response = await client.post(CREATE, json=tuned_body(models, *configs))

    assert response.status_code == 422
    assert response.json()["code"] == "DUPLICATE_MODEL_SELECTION"
    assert manager.jobs == []
    assert await count(db_session, SimulationRun) == 0
    assert await count(db_session, AIRequest) == 0

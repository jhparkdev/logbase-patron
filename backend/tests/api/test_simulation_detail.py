"""GET /api/simulations/{id} (S-04) 테스트. 화면이 5초마다 조회하는 진행·결과 응답을 확인한다."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.simulation_deps import get_simulation_manager
from app.models import RequestStatus
from app.openrouter.errors import USER_MESSAGES
from app.openrouter.errors import ErrorType as CallErrorType
from tests.api.simulation_helpers import (
    CREATE,
    FakeManager,
    build_manager,
    create_body,
)
from tests.db_helpers import Factory
from tests.services.simulation_fakes import FakeCaller, failed

R = RequestStatus
FAILURE_MESSAGE = USER_MESSAGES[CallErrorType.UNKNOWN_ERROR]


def detail_url(simulation_id: object) -> str:
    return f"{CREATE}/{simulation_id}"


async def run_to_the_end(
    app: FastAPI,
    client: AsyncClient,
    db_session: AsyncSession,
    factory: Factory,
    caller_of: Any,
) -> tuple[str, list[dict[str, Any]]]:
    """모델 2개를 가짜로 끝까지 돌리고 (실행 ID, 모델 행들)을 돌려준다."""
    rows = [dict(await factory.model(status="ACTIVE")) for _ in range(2)]
    manager = build_manager(db_session, caller_of(rows))
    app.dependency_overrides[get_simulation_manager] = lambda: manager
    response = await client.post(
        CREATE, json=create_body([r["model_id"] for r in rows])
    )
    await manager.wait_idle()
    return response.json()["simulation_id"], rows


# --- 끝난 실행 ---


@pytest.mark.usefixtures("poc_setup")
async def test_a_finished_run_shows_the_summary_and_every_slot(
    app: FastAPI,
    client: AsyncClient,
    factory: Factory,
    db_session: AsyncSession,
    signed_in: dict[str, Any],
) -> None:
    async def fail(kwargs: dict[str, Any]) -> Any:
        # 실제 클라이언트는 실패하면 정해진 사용자 문구를 함께 돌려준다
        return failed(R.FAILED).model_copy(update={"error_message": FAILURE_MESSAGE})

    simulation_id, rows = await run_to_the_end(
        app,
        client,
        db_session,
        factory,
        lambda rows: FakeCaller({rows[1]["openrouter_model_id"]: fail}),
    )

    response = await client.get(detail_url(simulation_id))

    assert response.status_code == 200
    body = response.json()
    summary = body["summary"]
    assert summary["simulation_id"] == simulation_id
    assert summary["status"] == "PARTIAL_SUCCESS"
    assert (summary["test_type"], summary["scenario_code"]) == ("CUSTOM", None)
    assert summary["model_count"] == 2
    assert summary["executed_by"] == signed_in["user_id"]
    assert summary["completed_at"] is not None
    assert (
        summary["final_result_count"],
        summary["success_count"],
        summary["failure_count"],
    ) == (2, 1, 1)
    # 비용 미확인 호출은 합계에 넣지 않고 따로 센다
    assert Decimal(summary["confirmed_cost_usd"]) == Decimal("0.001")
    assert summary["estimated_cost_usd"] is None
    assert summary["unknown_cost_count"] == 1
    assert summary["cost_check_status"] == "미확인 포함"

    first, second = body["results"]
    assert [first["slot_no"], second["slot_no"]] == [1, 2]
    assert (first["status"], first["error_type"]) == ("SUCCESS", None)
    assert Decimal(first["cost_usd"]) == Decimal("0.001")
    assert first["cost_status"] == "CONFIRMED"
    assert (first["input_tokens"], first["output_tokens"]) == (10, 5)
    assert (first["actual_provider"], first["actual_model"]) == ("P", "m")
    assert first["model_display_name_at_run"] == rows[0]["display_name"]
    assert first["model_status_at_run"] == "ACTIVE"
    assert first["execution_provider"] == "DeepInfra"
    assert first["execution_config"] == {"max_tokens": 4096}
    assert (first["json_parse_status"], first["schema_validation_status"]) == (
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
    )
    # 실패한 호출의 비용은 0 이 아니라 미확인(null)이다
    assert (second["status"], second["error_type"]) == ("FAILED", "UNKNOWN_ERROR")
    assert (second["cost_usd"], second["cost_status"]) == (None, "UNKNOWN")
    assert second["execution_provider"] == "DekaLLM"
    # 화면은 모델 칸에 응답 원문을 그대로 보여 준다. 실패한 칸은 원문이 없다
    assert first["response_text"] == "응답"
    assert second["response_text"] is None
    # 실패한 칸은 화면에 보여 줄 문구를 함께 준다. 내부 예외 원문이 아니라 정해진 사용자 문구다
    assert first["error_message"] is None
    assert second["error_message"] == FAILURE_MESSAGE


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_the_summary_total_equals_the_sum_of_the_slots(
    app: FastAPI, client: AsyncClient, factory: Factory, db_session: AsyncSession
) -> None:
    simulation_id, _ = await run_to_the_end(
        app, client, db_session, factory, lambda rows: FakeCaller()
    )

    body = (await client.get(detail_url(simulation_id))).json()

    confirmed = sum(
        Decimal(r["cost_usd"])
        for r in body["results"]
        if r["cost_status"] == "CONFIRMED"
    )
    assert Decimal(body["summary"]["confirmed_cost_usd"]) == confirmed
    assert Decimal(body["summary"]["total_cost_usd"]) == confirmed
    assert body["summary"]["cost_check_status"] == "확정"


@pytest.mark.usefixtures("signed_in")
async def test_the_total_adds_estimated_slots_and_leaves_out_unknown_ones(
    client: AsyncClient, factory: Factory
) -> None:
    run = await factory.simulation_run(status="PARTIAL_SUCCESS")
    # 추정 비용은 가격 근거가 있어야 기록된다(DB 제약)
    price_id = (await factory.model_price())["price_id"]
    slots = [
        ("CONFIRMED", Decimal("0.000123"), None),
        ("ESTIMATED", Decimal("0.000002"), price_id),
        ("UNKNOWN", None, None),
    ]
    for slot_no, (cost_status, cost, price) in enumerate(slots, start=1):
        request = await factory.ai_request(
            usage_origin="SIMULATION",
            simulation_id=run["simulation_id"],
            status="SUCCESS",
            cost_status=cost_status,
            cost_usd=cost,
            price_id=price,
        )
        await factory.simulation_result(
            simulation_id=run["simulation_id"],
            request_id=request["request_id"],
            slot_no=slot_no,
        )

    summary = (await client.get(detail_url(run["simulation_id"]))).json()["summary"]

    assert Decimal(summary["total_cost_usd"]) == Decimal("0.000125")
    assert summary["unknown_cost_count"] == 1
    assert summary["cost_check_status"] == "미확인 포함"


# --- 진행 중 ---


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_a_run_that_has_not_started_shows_pending_slots_and_no_cost(
    client: AsyncClient, manager: FakeManager, models: list[int]
) -> None:
    created = await client.post(CREATE, json=create_body(models))

    response = await client.get(detail_url(created.json()["simulation_id"]))

    body = response.json()
    assert body["summary"]["status"] == "PENDING"
    assert body["summary"]["completed_at"] is None
    assert body["summary"]["cost_check_status"] == "확인 중"
    assert [r["status"] for r in body["results"]] == ["PENDING", "PENDING"]
    for result in body["results"]:
        assert (result["cost_usd"], result["cost_status"]) == (None, "UNKNOWN")
        assert result["json_parse_status"] is None
        assert result["actual_provider"] is None
        # 아직 원문이 저장되지 않은 칸도 오류 없이 null 이다
        assert result["response_text"] is None


@pytest.mark.usefixtures("poc_setup", "signed_in")
async def test_only_the_final_attempt_of_a_slot_is_shown(
    client: AsyncClient,
    manager: FakeManager,
    models: list[int],
    factory: Factory,
) -> None:
    created = await client.post(CREATE, json=create_body(models))
    simulation_id = uuid.UUID(created.json()["simulation_id"])
    earlier = await factory.ai_request(
        usage_origin="SIMULATION", simulation_id=simulation_id, status="PENDING"
    )
    await factory.simulation_result(
        simulation_id=simulation_id,
        request_id=earlier["request_id"],
        model_id=models[0],
        slot_no=1,
        execution_provider="Earlier",
        is_final_attempt=False,
    )

    body = (await client.get(detail_url(simulation_id))).json()

    assert [r["slot_no"] for r in body["results"]] == [1, 2]
    assert earlier["request_id"] not in {r["request_id"] for r in body["results"]}
    assert body["summary"]["final_result_count"] == 2


# --- 거절 ---


@pytest.mark.usefixtures("signed_in")
async def test_an_unknown_run_is_404_without_needing_the_model_caller(
    client: AsyncClient,
) -> None:
    # 조회는 DB 만 읽는다. OpenRouter 클라이언트가 연결되기 전에도 동작해야 한다
    response = await client.get(detail_url(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["code"] == "SIMULATION_NOT_FOUND"


@pytest.mark.usefixtures("signed_in")
async def test_a_malformed_id_is_a_validation_error(client: AsyncClient) -> None:
    response = await client.get(detail_url("not-a-uuid"))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.usefixtures("signed_in")
async def test_a_late_answer_kept_for_reconciliation_is_not_shown(
    client: AsyncClient, factory: Factory
) -> None:
    # 취소 뒤 도착해 대조용으로만 남긴 원문은 화면의 결과가 아니다(J-03)
    run = (await factory.simulation_run(status="CANCELLED"))["simulation_id"]
    request = await factory.ai_request(
        usage_origin="SIMULATION", simulation_id=run, status="CANCELLED"
    )
    await factory.ai_request_payload(
        request_id=request["request_id"], response_text="늦은 응답"
    )
    await factory.simulation_result(simulation_id=run, request_id=request["request_id"])

    body = (await client.get(detail_url(run))).json()

    assert body["results"][0]["status"] == "CANCELLED"
    assert body["results"][0]["response_text"] is None

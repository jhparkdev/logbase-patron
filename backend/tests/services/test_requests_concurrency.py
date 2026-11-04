"""서로 다른 DB 연결에서 경쟁하는 상태 변경과 호출자 소유의 트랜잭션을 검증한다."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta

import pytest
from sqlalchemy import delete, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import AIRequest, APIKey, CostSource, Project, RequestStatus, Service
from app.services import requests
from tests.db_helpers import T0, Factory
from tests.services.request_helpers import FinishedRecord

FINISHED_AT = T0 + timedelta(seconds=42)
LOCK_WAIT_SECONDS = 5


@dataclass(frozen=True)
class RaceRequest:
    engine: AsyncEngine
    request_id: uuid.UUID


@pytest.fixture
async def committed_request(
    migrated_database: URL, request: pytest.FixtureRequest
) -> AsyncIterator[RaceRequest]:
    """다른 연결에서도 보이는 테스트 행을 만들고, 생성한 행만 종료 시 정리한다.

    일반 롤백 fixture의 미확정 행은 다른 연결에서 보이지 않아 경쟁을 재현할 수 없다.
    이 테스트만 준비 데이터를 commit하고, 종료 시 해당 ID의 임시 행만 제거한다.
    """
    engine = create_async_engine(migrated_database, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as setup:
            factory = Factory(setup)
            code = f"RACE-{uuid.uuid4().hex}"
            project = await factory.project(project_code=code)
            service = await factory.service(service_code=code)
            key = await factory.api_key(project_id=project["project_id"])
            row = await factory.ai_request(
                key_id=key["key_id"],
                project_id=project["project_id"],
                service_id=service["service_id"],
                status=getattr(request, "param", RequestStatus.RUNNING),
            )
            await setup.commit()
        try:
            yield RaceRequest(engine, row["request_id"])
        finally:
            # patron_test에 이 fixture가 만든 임시 행만 외래키의 역순으로 제거한다.
            async with engine.begin() as cleanup:
                await cleanup.execute(
                    delete(AIRequest).where(AIRequest.request_id == row["request_id"])
                )
                await cleanup.execute(
                    delete(APIKey).where(APIKey.key_id == key["key_id"])
                )
                await cleanup.execute(
                    delete(Service).where(Service.service_id == service["service_id"])
                )
                await cleanup.execute(
                    delete(Project).where(Project.project_id == project["project_id"])
                )
    finally:
        await engine.dispose()


async def change(session: AsyncSession, request_id: uuid.UUID, operation: str) -> bool:
    if operation == "finish":
        return await requests.record_finished(
            session,
            request_id,
            FinishedRecord(),
            FINISHED_AT,
            cost_source=CostSource.API_RESPONSE,
        )
    if operation == "cancel":
        return await requests.cancel_request(session, request_id, FINISHED_AT)
    if operation == "start":
        return await requests.mark_running(session, request_id, T0)
    raise AssertionError(f"지원하지 않는 테스트 작업: {operation}")


@pytest.mark.parametrize(
    ("committed_request", "first", "second", "second_changes", "final_status"),
    [
        (RequestStatus.RUNNING, "finish", "cancel", False, RequestStatus.SUCCESS),
        (RequestStatus.RUNNING, "cancel", "finish", False, RequestStatus.CANCELLED),
        (RequestStatus.RUNNING, "finish", "finish", False, RequestStatus.SUCCESS),
        # 시작은 종료 상태가 아니므로, 시작 직후 도착한 취소는 여전히 성공해야 한다.
        (RequestStatus.PENDING, "start", "cancel", True, RequestStatus.CANCELLED),
        (RequestStatus.PENDING, "cancel", "start", False, RequestStatus.CANCELLED),
    ],
    indirect=["committed_request"],
)
async def test_competing_updates_recheck_the_state_after_the_first_commits(
    committed_request: RaceRequest,
    first: str,
    second: str,
    second_changes: bool,
    final_status: RequestStatus,
) -> None:
    engine, request_id = committed_request.engine, committed_request.request_id
    async with AsyncSession(engine) as winner, AsyncSession(engine) as contender:
        winner_pid = await winner.scalar(text("SELECT pg_backend_pid()"))
        contender_pid = await contender.scalar(text("SELECT pg_backend_pid()"))
        assert winner_pid != contender_pid
        assert await change(winner, request_id, first)
        pending = asyncio.create_task(change(contender, request_id, second))
        try:
            # 시간 차이에 기대지 않고, 뒤의 UPDATE가 실제로 앞선 트랜잭션을 기다렸는지 확인한다.
            async with engine.connect() as observer:
                async with asyncio.timeout(LOCK_WAIT_SECONDS):
                    while winner_pid not in await observer.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": contender_pid}
                    ):
                        if pending.done():
                            pytest.fail(
                                "경쟁하는 갱신이 앞선 트랜잭션을 기다리지 않고 끝났습니다."
                            )
                        await asyncio.sleep(0.01)
            await winner.commit()
            assert await asyncio.wait_for(pending, LOCK_WAIT_SECONDS) is second_changes
            await contender.commit()
        finally:
            # 검증 중 실패해도 잠금을 기다리는 작업을 끝내야 세션과 임시 행을 정리할 수 있다.
            if not pending.done():
                pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

    async with engine.connect() as observer:
        row = (
            (
                await observer.execute(
                    text("SELECT * FROM ai_requests WHERE request_id = :id"),
                    {"id": request_id},
                )
            )
            .mappings()
            .one()
        )
    assert row["status"] == final_status
    if final_status == RequestStatus.SUCCESS:
        assert row["cost_usd"] == FinishedRecord().cost_usd
        assert row["input_tokens"] == FinishedRecord().input_tokens
        assert row["external_generation_id"] == FinishedRecord().external_generation_id
    else:
        assert row["cost_status"] == "UNKNOWN"
        assert row["cost_usd"] is None
        assert row["input_tokens"] is None
        assert row["external_generation_id"] is None


async def test_transition_is_not_committed_until_the_caller_decides(
    committed_request: RaceRequest,
) -> None:
    engine, request_id = committed_request.engine, committed_request.request_id
    query = text("SELECT status FROM ai_requests WHERE request_id = :id")
    async with AsyncSession(engine) as session:
        assert await requests.cancel_request(session, request_id, FINISHED_AT)
        # 함수가 내부에서 commit했다면 다른 연결에도 CANCELLED가 보여 이 검사가 실패한다.
        async with engine.connect() as observer:
            assert (
                await observer.scalar(query, {"id": request_id})
                == RequestStatus.RUNNING
            )
        await session.rollback()
    async with engine.connect() as observer:
        assert await observer.scalar(query, {"id": request_id}) == RequestStatus.RUNNING

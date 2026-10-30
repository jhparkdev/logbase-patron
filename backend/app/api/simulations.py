"""비교 실행(시뮬레이터) 라우터. 입력 검증·인증·응답 변환만 하고 규칙은 services 에 맡긴다."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import DevUserDep, NowDep
from app.api.simulation_deps import CancelDepsDep, SimulationManagerDep
from app.api.simulation_errors import SimulationRoute
from app.db import SessionDep
from app.schemas.simulation import SimulationAccepted, SimulationCreateRequest
from app.schemas.simulation_cancel import (
    RequestCancelOutcome,
    SimulationCancelResponse,
)
from app.schemas.simulation_error import SimulationErrorResponse
from app.schemas.simulation_history import (
    SimulationHistoryList,
    SimulationHistoryQuery,
    SimulationRerunDraft,
)
from app.schemas.simulation_result import SimulationDetailResponse
from app.services.simulation_cancel_service import (
    CancelReport,
    SimulationNotFoundError,
    cancel_simulation,
    cancel_slot,
)
from app.services.simulation_create import create_simulation
from app.services.simulation_detail import get_simulation_detail
from app.services.simulation_history import list_simulation_history
from app.services.simulation_lookup import DbSimulationLookup
from app.services.simulation_ports import IntakeDeps
from app.services.simulation_recorders import SessionRequestRecorder
from app.services.simulation_rerun import get_rerun_draft
from app.services.simulation_store import DbSimulationStore

router = APIRouter(
    prefix="/simulations", tags=["simulations"], route_class=SimulationRoute
)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": SimulationErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": SimulationErrorResponse},
    },
)
async def create_simulation_run(
    body: SimulationCreateRequest,
    request: Request,
    response: Response,
    user: DevUserDep,
    session: SessionDep,
    now: NowDep,
    manager: SimulationManagerDep,
) -> SimulationAccepted:
    """비교 실행을 접수하고 바로 돌려준다. 모델 호출은 응답 뒤 백그라운드에서 진행한다."""
    job = await create_simulation(
        body,
        executed_by=user.user_id,
        deps=IntakeDeps(
            lookup=DbSimulationLookup(session),
            recorder=SessionRequestRecorder(session),
            store=DbSimulationStore(session),
            now=lambda: now,
            new_id=uuid.uuid7,
        ),
    )
    # 저장을 확정한 뒤에 시작한다. 확정 전에 시작하면 백그라운드가 아직 보이지 않는 행을 갱신하려 하고,
    # 확정이 실패했는데 모델이 불려 비용만 나가는 일도 생긴다
    await session.commit()
    manager.start(job)
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{job.simulation_id}"
    return SimulationAccepted(simulation_id=job.simulation_id)


@router.get(
    "",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": SimulationErrorResponse}
    },
)
async def list_simulation_runs(
    query: Annotated[SimulationHistoryQuery, Query()],
    session: SessionDep,
    now: NowDep,
) -> SimulationHistoryList:
    """이력 목록. 조건으로 거른 결과를 최신 순으로 상한까지 준다. 정렬·페이지는 화면이 한다."""
    return await list_simulation_history(session, query, now)


@router.get(
    "/{simulation_id}",
    responses={status.HTTP_404_NOT_FOUND: {"model": SimulationErrorResponse}},
)
async def read_simulation_run(
    simulation_id: uuid.UUID, session: SessionDep
) -> SimulationDetailResponse:
    """진행·결과 조회. 화면이 끝날 때까지 5초마다 부른다. DB 만 읽으므로 비용이 들지 않는다."""
    detail = await get_simulation_detail(session, simulation_id)
    if detail is None:
        raise SimulationNotFoundError
    return detail


@router.get(
    "/{simulation_id}/rerun-draft",
    responses={status.HTTP_404_NOT_FOUND: {"model": SimulationErrorResponse}},
)
async def read_rerun_draft(
    simulation_id: uuid.UUID, session: SessionDep
) -> SimulationRerunDraft:
    """재실행 초안. 과거 입력으로 화면 입력칸을 채운다. 실행은 사용자가 새 실행 요청으로 보낼 때 시작한다."""
    draft = await get_rerun_draft(session, simulation_id)
    if draft is None:
        raise SimulationNotFoundError
    return draft


@router.post(
    "/{simulation_id}/cancel",
    responses={status.HTTP_404_NOT_FOUND: {"model": SimulationErrorResponse}},
)
async def cancel_simulation_run(
    simulation_id: uuid.UUID, deps: CancelDepsDep
) -> SimulationCancelResponse:
    """실행 전체를 취소한다. 이미 끝난 모델은 그대로 두고, 이미 끝난 실행도 오류가 아니라 현재 상태를 알려 준다."""
    return _to_cancel_response(await cancel_simulation(simulation_id, deps))


@router.post(
    "/{simulation_id}/slots/{slot_no}/cancel",
    responses={status.HTTP_404_NOT_FOUND: {"model": SimulationErrorResponse}},
)
async def cancel_simulation_slot(
    simulation_id: uuid.UUID, slot_no: int, deps: CancelDepsDep
) -> SimulationCancelResponse:
    """모델 하나만 취소한다. 나머지 모델은 계속 돈다."""
    return _to_cancel_response(await cancel_slot(simulation_id, slot_no, deps))


def _to_cancel_response(report: CancelReport) -> SimulationCancelResponse:
    return SimulationCancelResponse(
        simulation_id=report.simulation_id,
        status=report.status,
        results=[
            RequestCancelOutcome(
                request_id=outcome.request_id,
                slot_no=outcome.slot_no,
                decision=outcome.decision,
                status=outcome.status,
            )
            for outcome in report.outcomes
        ],
    )

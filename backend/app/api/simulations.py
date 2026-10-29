"""비교 실행(시뮬레이터) 라우터. 입력 검증·인증·응답 변환만 하고 규칙은 services 에 맡긴다."""

import uuid

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUserDep, NowDep
from app.api.simulation_deps import SimulationManagerDep
from app.api.simulation_errors import SimulationRoute
from app.db import SessionDep
from app.schemas.simulation import SimulationAccepted, SimulationCreateRequest
from app.schemas.simulation_error import SimulationErrorResponse
from app.services.simulation_create import create_simulation
from app.services.simulation_lookup import DbSimulationLookup
from app.services.simulation_ports import IntakeDeps
from app.services.simulation_recorders import SessionRequestRecorder
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
    user: CurrentUserDep,
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

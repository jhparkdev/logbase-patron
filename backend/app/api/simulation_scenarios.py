"""시나리오 목록 라우터. 시뮬레이터(P-04)의 시나리오 선택과 이력(P-05)의 시나리오 필터가 쓴다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.api.simulation_errors import SimulationRoute
from app.db import SessionDep
from app.schemas.simulation_error import SimulationRequestErrorResponse
from app.schemas.simulation_scenario import (
    ScenarioList,
    ScenarioListQuery,
    ScenarioRead,
)
from app.services.simulation_scenarios import list_scenarios

# main.py 는 라우터 단위 로그인 검사를 하지 않으므로, 시뮬레이터 라우터와 같게 여기서 세션을 요구한다.
router = APIRouter(
    prefix="/scenarios",
    tags=["simulations"],
    route_class=SimulationRoute,
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": SimulationRequestErrorResponse}
    },
)
async def list_simulation_scenarios(
    query: Annotated[ScenarioListQuery, Query()], session: SessionDep
) -> ScenarioList:
    rows = await list_scenarios(session, include_inactive=query.include_inactive)
    return ScenarioList(items=[ScenarioRead.model_validate(row) for row in rows])

"""진행·결과 조회(S-04). 읽기만 한다.

요약은 v_simulation_summary 가 계산한 값을 그대로 쓰고 여기서 다시 합산하지 않는다.
요약과 모델별 결과의 합계가 같은 데이터에서 나와야 어긋나지 않기 때문이다.
"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIRequest, SimulationResult
from app.schemas.simulation_result import (
    SimulationDetailResponse,
    SimulationModelResult,
    SimulationSummary,
)

_SUMMARY = text(
    "SELECT * FROM v_simulation_summary WHERE simulation_id = :simulation_id"
)


async def get_simulation_detail(
    session: AsyncSession, simulation_id: uuid.UUID
) -> SimulationDetailResponse | None:
    """실행 요약과 칸별 최종 결과. 없는 실행이면 None."""
    row = (
        (await session.execute(_SUMMARY, {"simulation_id": simulation_id}))
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return SimulationDetailResponse(
        summary=SimulationSummary.model_validate(dict(row)),
        results=await _final_results(session, simulation_id),
    )


async def _final_results(
    session: AsyncSession, simulation_id: uuid.UUID
) -> list[SimulationModelResult]:
    rows = await session.execute(
        select(SimulationResult, AIRequest)
        .join(AIRequest, AIRequest.request_id == SimulationResult.request_id)
        .where(
            SimulationResult.simulation_id == simulation_id,
            SimulationResult.is_final_attempt,
        )
        .order_by(SimulationResult.slot_no)
    )
    return [_to_model_result(result, request) for result, request in rows]


def _to_model_result(
    result: SimulationResult, request: AIRequest
) -> SimulationModelResult:
    return SimulationModelResult(
        slot_no=result.slot_no,
        request_id=result.request_id,
        model_id=result.model_id,
        model_display_name_at_run=result.model_display_name_at_run,
        model_status_at_run=result.model_status_at_run,
        execution_provider=result.execution_provider,
        actual_provider=request.actual_provider,
        actual_model=request.actual_model,
        status=request.status,
        error_type=request.error_type,
        latency_ms=request.latency_ms,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
        cost_usd=request.cost_usd,
        cost_status=request.cost_status,
        json_parse_status=result.json_parse_status,
        schema_validation_status=result.schema_validation_status,
        missing_required_fields=result.missing_required_fields,
        comparability_note=result.comparability_note,
    )

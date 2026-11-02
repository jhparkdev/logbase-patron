"""진행·결과 조회(S-04). 읽기만 한다.

요약은 v_simulation_summary 가 계산한 값을 그대로 쓰고 여기서 다시 합산하지 않는다.
요약과 모델별 결과의 합계가 같은 데이터에서 나와야 어긋나지 않기 때문이다.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    AIRequestPayload,
    OutputAsset,
    RequestStatus,
    SimulationResult,
)
from app.schemas.simulation_output import OutputImageRead
from app.schemas.simulation_result import (
    SimulationDetailResponse,
    SimulationModelResult,
    SimulationSummary,
)
from app.services.simulation_output_config import stored_output_type

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
        select(SimulationResult, AIRequest, AIRequestPayload.response_text)
        .join(AIRequest, AIRequest.request_id == SimulationResult.request_id)
        # 원문은 호출이 끝나야 저장되므로 진행 중인 칸에는 행이 없다
        .outerjoin(
            AIRequestPayload,
            AIRequestPayload.request_id == SimulationResult.request_id,
        )
        .where(
            SimulationResult.simulation_id == simulation_id,
            SimulationResult.is_final_attempt,
        )
        .order_by(SimulationResult.slot_no)
    )
    finals = rows.all()
    images = await _output_images(
        session, [result.request_id for result, _, _ in finals]
    )
    return [
        _to_model_result(result, request, response_text, images[result.request_id])
        for result, request, response_text in finals
    ]


async def _output_images(
    session: AsyncSession, request_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[OutputImageRead]]:
    """칸마다 만든 그림. 모델이 돌려준 순서다."""
    rows = await session.scalars(
        select(OutputAsset)
        .where(OutputAsset.request_id.in_(request_ids))
        .order_by(OutputAsset.request_id, OutputAsset.sort_order)
    )
    images: dict[uuid.UUID, list[OutputImageRead]] = defaultdict(list)
    for asset in rows:
        images[asset.request_id].append(
            OutputImageRead(
                output_asset_id=asset.output_asset_id,
                sort_order=asset.sort_order,
                mime_type=asset.mime_type,
                file_size_bytes=asset.file_size_bytes,
            )
        )
    return images


def _to_model_result(
    result: SimulationResult,
    request: AIRequest,
    response_text: str | None,
    output_images: list[OutputImageRead],
) -> SimulationModelResult:
    cancelled = request.status == RequestStatus.CANCELLED
    return SimulationModelResult(
        slot_no=result.slot_no,
        request_id=result.request_id,
        model_id=result.model_id,
        model_display_name_at_run=result.model_display_name_at_run,
        model_status_at_run=result.model_status_at_run,
        execution_provider=result.execution_provider,
        execution_config=request.execution_config,
        actual_provider=request.actual_provider,
        actual_model=request.actual_model,
        status=request.status,
        error_type=request.error_type,
        error_message=request.error_message,
        latency_ms=request.latency_ms,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
        cost_usd=request.cost_usd,
        cost_status=request.cost_status,
        json_parse_status=result.json_parse_status,
        schema_validation_status=result.schema_validation_status,
        missing_required_fields=result.missing_required_fields,
        comparability_note=result.comparability_note,
        # 취소된 칸의 원문·그림은 취소 뒤 늦게 도착해 대조용으로만 남긴 것이라 결과로 보여 주지 않는다
        response_text=None if cancelled else response_text,
        output_type=stored_output_type(request.execution_config),
        output_images=[] if cancelled else output_images,
    )

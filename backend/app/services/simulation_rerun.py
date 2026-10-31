"""재실행 초안(S-09). 읽기만 한다.

과거 실행의 입력을 그대로 돌려주어 화면이 입력칸을 채우게 한다. 지금 규칙으로 다시 거절하지 않고,
사용자가 고쳐 보낸 새 실행 요청을 접수할 때 검증한다(simulation_create.py).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AIRequest,
    InputAsset,
    ModelRegistry,
    ModelStatus,
    SimulationResult,
    SimulationRun,
    SimulationRunAsset,
)
from app.schemas.simulation import RoutingPolicy
from app.schemas.simulation_history import (
    RerunBlockReason,
    RerunModel,
    RerunRoutingPolicy,
    SimulationRerunDraft,
)
from app.services.image_storage import ImageStorage
from app.services.simulation_validation import is_model_selectable


@dataclass(frozen=True)
class PastSlot:
    """과거 실행의 모델 한 칸(최종 시도)과 그 모델의 현재 이름·상태."""

    model_id: int
    execution_provider: str
    execution_config: dict[str, Any]  # 이 칸에 실제로 적용했던 설정
    current_display_name: str
    current_status: ModelStatus


def build_rerun_draft(
    run: SimulationRun,
    slots: Sequence[PastSlot],
    *,
    asset_ids: Sequence[uuid.UUID] = (),
    assets_available: bool = True,
) -> SimulationRerunDraft:
    """과거 실행 행과 칸들로 초안을 만든다. slots 는 칸 번호 순서, asset_ids 는 올린 순서여야 한다.

    이미지 파일을 더는 구할 수 없으면 막는다. 같은 입력이 아닌 채로 돌리면 비교가 달라지기 때문이다.
    """
    blocked = (
        RerunBlockReason.INPUT_MISSING if asset_ids and not assets_available else None
    )
    return SimulationRerunDraft(
        rerun_of_simulation_id=run.simulation_id,
        test_type=run.test_type,
        scenario_id=run.scenario_id,
        prompt_text=run.prompt_text,
        input_text=run.input_text,
        json_schema=run.json_schema,
        execution_config=run.execution_config,
        routing_policy=RerunRoutingPolicy(
            # 값이 없던 기록은 새 실행의 기본값으로 읽는다
            allow_fallbacks=run.routing_policy.get(
                "allow_fallbacks", RoutingPolicy().allow_fallbacks
            )
        ),
        models=[_to_rerun_model(slot) for slot in slots],
        asset_ids=list(asset_ids),
        rerunnable=blocked is None,
        blocked_reason=blocked,
    )


def _to_rerun_model(slot: PastSlot) -> RerunModel:
    return RerunModel(
        model_id=slot.model_id,
        execution_provider=slot.execution_provider,
        execution_config=slot.execution_config,
        current_display_name=slot.current_display_name,
        current_status=slot.current_status,
        selectable=is_model_selectable(slot.current_status),
    )


async def get_rerun_draft(
    session: AsyncSession, simulation_id: uuid.UUID, storage: ImageStorage
) -> SimulationRerunDraft | None:
    """재실행 초안. 없는 실행이면 None."""
    run = await session.get(SimulationRun, simulation_id)
    if run is None:
        return None
    assets = await _past_assets(session, simulation_id)
    return build_rerun_draft(
        run,
        await _past_slots(session, simulation_id),
        asset_ids=[asset_id for asset_id, _ in assets],
        assets_available=all([await storage.exists(path) for _, path in assets]),
    )


async def _past_assets(
    session: AsyncSession, simulation_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    """과거 실행에 쓴 이미지의 (asset_id, 저장 경로). 올린 순서다."""
    rows = await session.execute(
        select(InputAsset.asset_id, InputAsset.storage_path)
        .join(
            SimulationRunAsset,
            SimulationRunAsset.asset_id == InputAsset.asset_id,
        )
        .where(SimulationRunAsset.simulation_id == simulation_id)
        .order_by(SimulationRunAsset.sort_order)
    )
    return [(asset_id, path) for asset_id, path in rows]


async def _past_slots(
    session: AsyncSession, simulation_id: uuid.UUID
) -> list[PastSlot]:
    rows = await session.execute(
        select(
            SimulationResult.model_id,
            SimulationResult.execution_provider,
            AIRequest.execution_config,
            ModelRegistry.display_name,
            ModelRegistry.status,
        )
        .join(ModelRegistry, ModelRegistry.model_id == SimulationResult.model_id)
        .join(AIRequest, AIRequest.request_id == SimulationResult.request_id)
        .where(
            SimulationResult.simulation_id == simulation_id,
            SimulationResult.is_final_attempt,
        )
        .order_by(SimulationResult.slot_no)
    )
    return [
        PastSlot(
            model_id=model_id,
            execution_provider=provider,
            execution_config=config,
            current_display_name=name,
            current_status=ModelStatus(status),
        )
        for model_id, provider, config, name, status in rows
    ]

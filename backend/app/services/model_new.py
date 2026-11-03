"""신규 모델 알림(P-03). 최근에 올라왔고 아직 등록하지 않은 OpenRouter 모델을 찾는다.

OpenRouter는 새 모델을 푸시로 알려 주지 않는다. 받아 둔 목록(openrouter_catalog)에서 올라온 시각
(created)이 기간 안인 모델 중 우리에게 없는 것을 골라, 따로 "본 모델"을 저장하지 않는다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.openrouter.lookup_result import ModelInfo
from app.services import model_search


@dataclass(frozen=True)
class NewModel:
    model: ModelInfo
    # model.created_at과 같은 값. 새 모델은 올라온 시각을 아는 모델만이라 None이 아니다
    created_at: datetime


@dataclass(frozen=True)
class NewModels:
    items: list[NewModel]
    # limit과 관계없이 조건에 맞는 전체 개수
    total: int


async def find_new_models(
    session: AsyncSession,
    models: Sequence[ModelInfo],
    *,
    now: datetime,
    days: int,
    limit: int,
) -> NewModels:
    """days일 안에 올라온 미등록 모델을 최근 순(같으면 모델 ID순)으로 limit개까지 돌려준다.

    올라온 시각을 모르는 모델은 새 모델인지 알 수 없어 뺀다. 기간의 경계(정확히 days일 전)는 포함한다.
    """
    since = now - timedelta(days=days)
    recent = [
        NewModel(model=model, created_at=model.created_at)
        for model in models
        if model.created_at is not None and model.created_at >= since
    ]
    registered = await model_search.find_registered(
        session, [entry.model.model_id for entry in recent]
    )
    fresh = [entry for entry in recent if entry.model.model_id not in registered]
    fresh.sort(key=lambda entry: (-entry.created_at.timestamp(), entry.model.model_id))
    return NewModels(items=fresh[:limit], total=len(fresh))

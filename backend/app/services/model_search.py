"""OpenRouter 모델 검색(P-03). 받아 온 목록에서 찾고, 이미 등록된 모델을 가려낸다."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelRegistry
from app.openrouter.lookup_result import ModelInfo


@dataclass(frozen=True)
class SearchPage:
    items: list[ModelInfo]
    total: int


def search_models(
    models: Sequence[ModelInfo], *, q: str | None, page: int, page_size: int
) -> SearchPage:
    """q가 모델 ID나 이름에 들어 있는 모델을 모델 ID순으로 한 페이지만 돌려준다.

    대소문자는 구분하지 않는다. total은 찾은 전체 개수다.
    """
    found = list(models)
    if q:
        needle = q.casefold()
        found = [
            model
            for model in found
            if needle in model.model_id.casefold()
            or needle in (model.name or "").casefold()
        ]
    found.sort(key=lambda model: model.model_id)
    start = (page - 1) * page_size
    return SearchPage(items=found[start : start + page_size], total=len(found))


async def find_registered(
    session: AsyncSession, openrouter_model_ids: Collection[str]
) -> set[str]:
    """이미 등록된 모델의 OpenRouter 모델 ID만 돌려준다."""
    if not openrouter_model_ids:
        return set()
    rows = await session.scalars(
        select(ModelRegistry.openrouter_model_id).where(
            ModelRegistry.openrouter_model_id.in_(openrouter_model_ids)
        )
    )
    return set(rows)

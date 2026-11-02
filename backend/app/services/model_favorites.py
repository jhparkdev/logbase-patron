from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelRegistry, UserModelFavorite


class FavoriteModelNotFoundError(LookupError):
    """등록되지 않은 모델을 즐겨찾기하려 했다."""


async def list_favorites(
    session: AsyncSession, user_id: int
) -> list[UserModelFavorite]:
    """최근에 등록한 순서다. 같은 시각이면 모델·Provider 순으로 고정해 순서가 흔들리지 않게 한다."""
    result = await session.scalars(
        select(UserModelFavorite)
        .where(UserModelFavorite.user_id == user_id)
        .order_by(
            UserModelFavorite.created_at.desc(),
            UserModelFavorite.model_id,
            UserModelFavorite.execution_provider,
        )
    )
    return list(result)


async def add_favorite(
    session: AsyncSession, user_id: int, model_id: int, execution_provider: str
) -> tuple[UserModelFavorite, bool]:
    """즐겨찾기를 등록한다. 이미 있으면 그대로 돌려주며, 새로 만들었는지를 함께 알려 준다."""
    if await session.get(ModelRegistry, model_id) is None:
        raise FavoriteModelNotFoundError
    inserted = await session.scalar(
        insert(UserModelFavorite)
        .values(
            user_id=user_id, model_id=model_id, execution_provider=execution_provider
        )
        .on_conflict_do_nothing()
        .returning(UserModelFavorite)
    )
    if inserted is not None:
        return inserted, True
    existing = await session.get(
        UserModelFavorite, (user_id, model_id, execution_provider)
    )
    assert existing is not None  # 충돌했으므로 같은 키의 행이 있다
    return existing, False


async def remove_favorite(
    session: AsyncSession, user_id: int, model_id: int, execution_provider: str
) -> None:
    """내 즐겨찾기 한 건만 지운다. 없어도 오류가 아니다. 이력이 아니라 사용자 설정이라 삭제가 허용된다."""
    await session.execute(
        delete(UserModelFavorite).where(
            UserModelFavorite.user_id == user_id,
            UserModelFavorite.model_id == model_id,
            UserModelFavorite.execution_provider == execution_provider,
        )
    )

"""등록 모델 목록 조회(P-03). 검색 조건, 정렬, 페이지를 DB에서 처리한다."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import ModelPrice, ModelRegistry


@dataclass(frozen=True)
class ModelListItem:
    model: ModelRegistry
    price: ModelPrice | None


@dataclass(frozen=True)
class ModelPage:
    items: list[ModelListItem]
    total: int


async def list_models(
    session: AsyncSession,
    *,
    name: str | None,
    model_id: str | None,
    provider: str | None,
    statuses: Sequence[str],
    sort: str,
    descending: bool,
    page: int,
    page_size: int,
) -> ModelPage:
    """조건에 맞는 모델을 한 페이지만 돌려준다. total은 조건에 맞는 전체 개수다.

    sort는 호출하는 쪽이 허용 목록(ModelSortField)으로 이미 검증한 값이다.
    """
    # 현재 가격 = 종료되지 않은 모델 대표가격(실행 업체가 비어 있는 행). 모델마다 최대 1개다.
    price = aliased(ModelPrice)
    sort_columns: dict[str, ColumnElement[object]] = {
        "display_name": ModelRegistry.display_name,
        "openrouter_model_id": ModelRegistry.openrouter_model_id,
        "provider": ModelRegistry.provider,
        "input_modalities": func.array_to_string(ModelRegistry.input_modalities, ","),
        "price_input": price.input_price_per_token,
        "price_output": price.output_price_per_token,
        "status": ModelRegistry.status,
        "last_test_at": ModelRegistry.last_test_at,
        "last_test_status": ModelRegistry.last_test_status,
        "purpose": ModelRegistry.purpose,
        "created_at": ModelRegistry.created_at,
        "updated_at": ModelRegistry.updated_at,
    }

    # %와 _는 검색 기호가 아니라 글자 그대로 찾는다(autoescape).
    conditions: list[ColumnElement[bool]] = []
    if name:
        conditions.append(ModelRegistry.display_name.icontains(name, autoescape=True))
    if model_id:
        conditions.append(
            ModelRegistry.openrouter_model_id.icontains(model_id, autoescape=True)
        )
    if provider:
        conditions.append(ModelRegistry.provider.icontains(provider, autoescape=True))
    if statuses:
        conditions.append(ModelRegistry.status.in_(statuses))

    total = await session.scalar(
        select(func.count()).select_from(ModelRegistry).where(*conditions)
    )

    # 문자열 정렬 순서는 DB의 정렬 규칙(collation)을 따른다. 이 개발 DB에서는 한글을 여러 글자로
    # 비교하면 가나다순과 다를 수 있다(예: '활성'이 '비활성'보다 앞). 영문 이름에는 영향이 없다.
    # 한글 이름을 많이 쓰게 되면 DB 정렬 규칙을 정해야 한다(DB 담당과 확인).
    column = sort_columns[sort]
    direction = column.desc() if descending else column.asc()
    statement = (
        select(ModelRegistry, price)
        .outerjoin(
            price,
            and_(
                price.model_id == ModelRegistry.model_id,
                price.effective_to.is_(None),
                price.execution_provider.is_(None),
            ),
        )
        .where(*conditions)
        # 값이 없는 행은 방향과 상관없이 뒤에 두고, 같은 값끼리는 ID순이라 페이지가 흔들리지 않는다.
        .order_by(direction.nulls_last(), ModelRegistry.model_id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await session.execute(statement)).all()
    return ModelPage(
        items=[ModelListItem(model, current) for model, current in rows],
        total=total or 0,
    )

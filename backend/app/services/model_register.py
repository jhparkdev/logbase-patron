"""OpenRouter 모델을 TESTING 상태로 등록한다(P-03). 저장은 한 번의 commit으로 끝낸다.

모델 정보(입출력 형식, 지원 설정, 글자 수 한도, 단가)는 요청이 아니라 OpenRouter 목록에서 채운다.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChangeAction,
    ChangeLog,
    ModelPrice,
    ModelRegistry,
    ModelStatus,
    PriceSource,
    PriceStatus,
)
from app.openrouter.lookup_result import ModelInfo
from app.services.model_registry import provider_from_model_id, snapshot_from_pricing

ENTITY_TYPE = "models"
CREATE_REASON = "모델 등록"


class ModelNotInOpenRouterError(LookupError):
    """OpenRouter 모델 목록에 없는 모델이다."""


class ModelAlreadyRegisteredError(ValueError):
    """이미 등록된 모델이다."""


async def register_model(
    session: AsyncSession,
    models: Sequence[ModelInfo],
    *,
    openrouter_model_id: str,
    display_name: str,
    purpose: str | None,
    user_id: int,
    now: datetime,
) -> int:
    """모델을 등록하고 새 모델 번호를 돌려준다."""
    info = next(
        (model for model in models if model.model_id == openrouter_model_id), None
    )
    provider = provider_from_model_id(openrouter_model_id)
    if info is None or provider is None:
        raise ModelNotInOpenRouterError

    # 같은 모델을 동시에 등록해도 한 건만 들어가도록, 이미 있으면 아무것도 넣지 않는 INSERT로 처리한다.
    model_id = await session.scalar(
        insert(ModelRegistry)
        .values(
            openrouter_model_id=openrouter_model_id,
            provider=provider,
            display_name=display_name,
            purpose=purpose,
            status=ModelStatus.TESTING.value,
            input_modalities=info.input_modalities,
            output_modalities=info.output_modalities,
            supported_parameters=info.supported_parameters,
            # 글자 수 한도는 0보다 커야 저장할 수 있다. 0 이하로 오면 모르는 것으로 둔다.
            context_length=_positive_or_none(info.context_length),
            metadata_fetched_at=now,
            created_by=user_id,
        )
        .on_conflict_do_nothing(index_elements=["openrouter_model_id"])
        .returning(ModelRegistry.model_id)
    )
    if model_id is None:
        raise ModelAlreadyRegisteredError

    _add_first_price(session, model_id, info, now)
    session.add(
        ChangeLog(
            entity_type=ENTITY_TYPE,
            entity_id=str(model_id),
            action=ChangeAction.CREATE.value,
            changes={
                "openrouter_model_id": {"old": None, "new": openrouter_model_id},
                "display_name": {"old": None, "new": display_name},
                "status": {"old": None, "new": ModelStatus.TESTING.value},
            },
            reason=CREATE_REASON,
            changed_by=user_id,
        )
    )
    await session.commit()
    return model_id


def _positive_or_none(value: int | None) -> int | None:
    return value if value is not None and value > 0 else None


def _add_first_price(
    session: AsyncSession, model_id: int, info: ModelInfo, now: datetime
) -> None:
    """단가를 알면 첫 가격 이력을 넣는다. 모르면 넣지 않아, 모델의 현재 가격이 없는(미확인) 상태가 된다."""
    snapshot = snapshot_from_pricing(info.pricing)
    if snapshot is None:
        return
    session.add(
        ModelPrice(
            model_id=model_id,
            price_status=PriceStatus.KNOWN.value,
            input_price_per_token=snapshot.input_price_per_token,
            output_price_per_token=snapshot.output_price_per_token,
            cache_read_price_per_token=snapshot.cache_read_price_per_token,
            cache_write_price_per_token=snapshot.cache_write_price_per_token,
            # str()은 작은 값을 1E-7처럼 쓰므로, OpenRouter가 준 표기와 같게 일반 숫자 표기로 남긴다.
            raw_pricing={
                key: format(value, "f") for key, value in info.pricing.items()
            },
            source=PriceSource.OPENROUTER_MODELS.value,
            effective_from=now,
            checked_at=now,
        )
    )

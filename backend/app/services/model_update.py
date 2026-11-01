"""등록 모델의 표시 이름·용도 수정과 상태 변경(P-03). 바뀐 내용은 change_logs에 남기고 한 번에 commit한다."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChangeAction, ChangeLog, ModelRegistry, ModelStatus
from app.services.model_registry import StatusChangeError, check_status_change

ENTITY_TYPE = "models"
UPDATE_REASON = "모델 정보 수정"
STATUS_REASON = "모델 상태 변경"


class ModelNotFoundError(LookupError):
    """수정할 모델이 없다."""


class StatusChangeRefusedError(ValueError):
    """상태를 바꿀 수 없다. reason에 거절 사유가 들어 있다."""

    def __init__(self, reason: StatusChangeError) -> None:
        super().__init__(reason)
        self.reason = reason


async def update_model(
    session: AsyncSession,
    model_id: int,
    changes: Mapping[str, str | None],
    user_id: int,
) -> None:
    """changes에 있는 항목(display_name, purpose)만 바꾼다. 값이 같으면 이력도 남기지 않는다."""
    model = await _lock_model(session, model_id)
    logged: dict[str, Any] = {}
    for field, new in changes.items():
        old = getattr(model, field)
        if old != new:
            setattr(model, field, new)
            logged[field] = {"old": old, "new": new}
    _log(session, model_id, ChangeAction.UPDATE, logged, UPDATE_REASON, user_id)
    await session.commit()


async def change_status(
    session: AsyncSession,
    model_id: int,
    target: ModelStatus,
    user_id: int,
    now: datetime,
) -> None:
    """허용된 상태 전이만 바꾼다. 거절되면 아무것도 바꾸지 않는다."""
    model = await _lock_model(session, model_id)
    refused = check_status_change(model.status, target, model.last_success_test_at, now)
    if refused is not None:
        raise StatusChangeRefusedError(refused)

    old = model.status
    model.status = target.value
    # 허용된 전이의 도착 상태는 ACTIVE 또는 INACTIVE뿐이다.
    if target == ModelStatus.ACTIVE:
        model.activated_at = now
    else:
        model.deactivated_at = now
    _log(
        session,
        model_id,
        ChangeAction.STATUS_CHANGE,
        {"status": {"old": old, "new": target.value}},
        STATUS_REASON,
        user_id,
    )
    await session.commit()


async def _lock_model(session: AsyncSession, model_id: int) -> ModelRegistry:
    """같은 모델의 동시 수정을 줄 세우려고 행을 잠그고 가져온다."""
    model = await session.get(ModelRegistry, model_id, with_for_update=True)
    if model is None:
        raise ModelNotFoundError
    return model


def _log(
    session: AsyncSession,
    model_id: int,
    action: ChangeAction,
    changes: dict[str, Any],
    reason: str,
    user_id: int,
) -> None:
    if not changes:
        return
    session.add(
        ChangeLog(
            entity_type=ENTITY_TYPE,
            entity_id=str(model_id),
            action=action.value,
            changes=changes,
            reason=reason,
            changed_by=user_id,
        )
    )

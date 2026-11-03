"""호출 비용이 정해지는 경로. 현재 시각을 인자로 받는 순수 판단이다.

- 응답에 비용이 있으면 끝난 시각에 확정(CONFIRMED, API_RESPONSE)
- 응답에 비용이 없으면 미확인(UNKNOWN, 금액 NULL)으로 두었다가, RECONCILE_DELAY가 지나면
  generation 조회로 대조해 확정한다(GENERATION_LOOKUP, reconciled_at 기록)
- 가격 추정은 근거 가격(price_id)과 함께 ESTIMATED로 둔다
- 라우팅 단계에서 거절된 실패(404)는 청구가 없음을 확인한 0원(NO_CHARGE)이고,
  그 밖의 실패는 청구 여부를 모르므로 UNKNOWN이다. 0원으로 적지 않는다.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from random import Random

from app.mock_data.outcomes import Outcome
from app.mock_data.rows import Row
from app.models import CostSource, CostStatus, ErrorType, RequestStatus

RECONCILE_DELAY = timedelta(days=2)
MISSING_COST_SHARE = 0.025
ESTIMATED_SHARE = 0.01


class CostPath(StrEnum):
    API_RESPONSE = "API_RESPONSE"
    MISSING = "MISSING"
    ESTIMATED = "ESTIMATED"


def sample_cost_path(rng: Random) -> CostPath:
    draw = rng.random()
    if draw < MISSING_COST_SHARE:
        return CostPath.MISSING
    if draw < MISSING_COST_SHARE + ESTIMATED_SHARE:
        return CostPath.ESTIMATED
    return CostPath.API_RESPONSE


def _fields(
    cost: Decimal | None,
    status: CostStatus,
    source: CostSource | None,
    *,
    price_id: int | None = None,
    confirmed_at: datetime | None = None,
    reconciled_at: datetime | None = None,
) -> Row:
    return {
        "cost_usd": cost,
        "cost_status": status,
        "cost_source": source,
        "price_id": price_id,
        "cost_confirmed_at": confirmed_at,
        "reconciled_at": reconciled_at,
    }


def cost_fields(
    outcome: Outcome,
    path: CostPath,
    cost: Decimal,
    completed_at: datetime,
    price_id: int,
    now: datetime,
) -> Row:
    if outcome.status != RequestStatus.SUCCESS:
        if outcome.error_type == ErrorType.UNSUPPORTED_INPUT:
            return _fields(
                Decimal(0),
                CostStatus.CONFIRMED,
                CostSource.NO_CHARGE,
                confirmed_at=completed_at,
            )
        return _fields(None, CostStatus.UNKNOWN, None)
    if path == CostPath.ESTIMATED:
        return _fields(
            cost, CostStatus.ESTIMATED, CostSource.PRICE_ESTIMATE, price_id=price_id
        )
    if path == CostPath.MISSING:
        if now - completed_at < RECONCILE_DELAY:
            return _fields(None, CostStatus.UNKNOWN, None)
        reconciled_at = completed_at + RECONCILE_DELAY
        return _fields(
            cost,
            CostStatus.CONFIRMED,
            CostSource.GENERATION_LOOKUP,
            confirmed_at=reconciled_at,
            reconciled_at=reconciled_at,
        )
    return _fields(
        cost, CostStatus.CONFIRMED, CostSource.API_RESPONSE, confirmed_at=completed_at
    )

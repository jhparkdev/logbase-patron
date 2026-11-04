"""비용 대조 기록: 호출 비용 정정 이력, PoC Key 사용량 스냅샷, OpenRouter 사용량과 Patron 기록의 대조.

OpenRouter 쪽 사용량에는 Patron이 금액을 모르는 호출(timeout·취소)의 과금이 섞여 있어 차액이 생긴다.
차액은 개별 호출에 배분하지 않고 대조 결과에만 남긴다.
"""

from datetime import datetime
from decimal import Decimal
from itertools import pairwise

from app.mock_data.keys import poc_key, production_key
from app.mock_data.organizations import AI_PDP
from app.mock_data.period import kst
from app.mock_data.rows import Row
from app.models import (
    Comparability,
    CostSource,
    CostStatus,
    ReconciliationStatus,
    RequestStatus,
)

ADJUSTMENT_REASON = "응답에 비용이 없어 Generation 조회로 확정"
# Patron이 금액을 모르는 timeout·취소 호출에 OpenRouter가 매긴 것으로 보는 과금(1건당)
UNSEEN_CHARGE_USD = Decimal("0.0004")
UNSEEN_CHARGE_STATUSES = {RequestStatus.TIMEOUT, RequestStatus.CANCELLED}
SNAPSHOT_TIMES = (kst(8, 1), kst(9, 1), kst(10, 1), kst(11, 1), kst(11, 6, 8))
SNAPSHOT_NOTE = {"note": "label, hash 등 Key 일부가 담긴 필드는 제거 후 저장"}
COMPARABLE_NOTE = "차액은 Timeout·취소 호출의 과금으로 추정. 개별 호출에 배분하지 않음"
UNCOMPARABLE_NOTE = "Mock Key라 OpenRouter 스냅샷이 없음 (비교 불가 예시)"


def cost_adjustment_rows(requests: list[Row]) -> list[Row]:
    reconciled = sorted(
        (r for r in requests if r["reconciled_at"] is not None),
        key=lambda r: r["reconciled_at"],
    )
    return [
        {
            "adjustment_id": number,
            "request_id": r["request_id"],
            "old_cost_usd": None,
            "new_cost_usd": r["cost_usd"],
            "old_cost_status": CostStatus.UNKNOWN,
            "new_cost_status": r["cost_status"],
            "old_cost_source": None,
            "new_cost_source": CostSource.GENERATION_LOOKUP,
            "reason": ADJUSTMENT_REASON,
            "adjusted_by_user_id": None,  # 시스템 정산
            "adjusted_at": r["reconciled_at"],
        }
        for number, r in enumerate(reconciled, start=1)
    ]


def _external_charge(row: Row) -> Decimal:
    """OpenRouter가 이 호출에 매긴 것으로 보는 금액."""
    if row["cost_usd"] is not None:
        return row["cost_usd"]
    return UNSEEN_CHARGE_USD if row["status"] in UNSEEN_CHARGE_STATUSES else Decimal(0)


def _spent_before(requests: list[Row], key_id: int, at: datetime) -> Decimal:
    return sum(
        (
            _external_charge(r)
            for r in requests
            if r["key_id"] == key_id and r["requested_at"] < at
        ),
        Decimal(0),
    )


def key_usage_snapshot_rows(requests: list[Row]) -> list[Row]:
    key = poc_key()
    if key.limit_usd is None:
        raise ValueError("PoC Key에는 사용 한도가 있어야 남은 한도를 계산할 수 있다")
    rows: list[Row] = []
    for number, at in enumerate(SNAPSHOT_TIMES, start=1):
        total = _spent_before(requests, key.key_id, at)
        month_start = at.replace(day=1, hour=0, minute=0)
        rows.append(
            {
                "snapshot_id": number,
                "key_id": key.key_id,
                "captured_at": at,
                "usage_total_usd": total,
                "usage_daily_usd": None,
                "usage_weekly_usd": None,
                "usage_monthly_usd": total
                - _spent_before(requests, key.key_id, month_start),
                "limit_usd": key.limit_usd,
                "limit_remaining_usd": key.limit_usd - total,
                "raw_response": SNAPSHOT_NOTE,
            }
        )
    return rows


def _patron_totals(
    requests: list[Row], key_id: int, start: datetime, end: datetime
) -> Row:
    calls = [
        r
        for r in requests
        if r["key_id"] == key_id and start <= r["requested_at"] < end
    ]

    def total(status: CostStatus) -> Decimal:
        return sum(
            (r["cost_usd"] for r in calls if r["cost_status"] == status), Decimal(0)
        )

    return {
        "patron_confirmed_usd": total(CostStatus.CONFIRMED),
        "patron_estimated_usd": total(CostStatus.ESTIMATED),
        "patron_unknown_count": sum(
            1 for r in calls if r["cost_status"] == CostStatus.UNKNOWN
        ),
    }


def usage_reconciliation_rows(requests: list[Row], snapshots: list[Row]) -> list[Row]:
    rows: list[Row] = []
    # 이어진 스냅샷 쌍마다 대조한다(9월·10월은 검토 완료, 진행 중인 11월은 열린 상태).
    for start, end in pairwise(snapshots[1:]):
        patron = _patron_totals(
            requests, start["key_id"], start["captured_at"], end["captured_at"]
        )
        external = end["usage_total_usd"] - start["usage_total_usd"]
        finished = end["captured_at"] < SNAPSHOT_TIMES[-1]
        rows.append(
            {
                "reconciliation_id": len(rows) + 1,
                "key_id": start["key_id"],
                "period_start": start["captured_at"],
                "period_end": end["captured_at"],
                "start_snapshot_id": start["snapshot_id"],
                "end_snapshot_id": end["snapshot_id"],
                "external_usage_usd": external,
                **patron,
                "difference_usd": external
                - patron["patron_confirmed_usd"]
                - patron["patron_estimated_usd"],
                "comparability": Comparability.COMPARABLE,
                "status": ReconciliationStatus.REVIEWED
                if finished
                else ReconciliationStatus.OPEN,
                "note": COMPARABLE_NOTE,
                "created_by": 1,
            }
        )
    mock_key = production_key(1, AI_PDP)
    start, end = kst(10, 1), kst(11, 1)
    rows.append(
        {
            "reconciliation_id": len(rows) + 1,
            "key_id": mock_key.key_id,
            "period_start": start,
            "period_end": end,
            "start_snapshot_id": None,
            "end_snapshot_id": None,
            "external_usage_usd": None,
            **_patron_totals(requests, mock_key.key_id, start, end),
            "difference_usd": None,
            "comparability": Comparability.UNCOMPARABLE,
            "status": ReconciliationStatus.OPEN,
            "note": UNCOMPARABLE_NOTE,
            "created_by": 1,
        }
    )
    return rows

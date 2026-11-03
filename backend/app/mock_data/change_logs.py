"""변경 이력(change_logs). 다른 생성기의 일정(모델·고객·구성원·예산·시나리오)과 같은 시각에 남긴다."""

from datetime import datetime, timedelta

from pydantic import JsonValue

from app.mock_data.budgets import BUDGETS, OCTOBER, SEPTEMBER
from app.mock_data.keys import KEYS
from app.mock_data.members import USERS
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import CUSTOMERS
from app.mock_data.period import PERIOD_START, kst
from app.mock_data.rows import Row
from app.mock_data.scenarios import (
    CHANGED_AT,
    DATA_SUMMARY_PROMPT_BEFORE_CHANGE,
    by_code,
)
from app.models import ChangeAction, KeyStatus, ModelStatus

ADMIN = 1
CONTRACT_LEAD = timedelta(days=1)  # 고객 등록은 사용 시작 하루 전에 한다


def _change(old: JsonValue, new: JsonValue) -> dict[str, JsonValue]:
    return {"old": old, "new": new}


def _entry(
    entity_type: str,
    entity_id: int,
    action: ChangeAction,
    changes: dict[str, JsonValue],
    reason: str,
    changed_by: int,
    changed_at: datetime,
) -> Row:
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "action": action,
        "changes": changes,
        "reason": reason,
        "changed_by": changed_by,
        "changed_at": changed_at,
    }


def _actor(preferred: int, at: datetime) -> int:
    member = next(u for u in USERS if u.user_id == preferred)
    return preferred if member.can_act_at(at) else ADMIN


def _model_entries() -> list[Row]:
    names = {
        p.openrouter_model_id: p.openrouter_model_id.split("/")[1] for p in MODEL_PLANS
    }
    rows: list[Row] = []
    for plan in MODEL_PLANS:
        status = {"status": _change(None, ModelStatus.TESTING)}
        rows.append(
            _entry(
                "models",
                plan.model_id,
                ChangeAction.CREATE,
                status,
                "모델 등록",
                plan.created_by,
                plan.registered_at,
            )
        )
        if plan.activated_at is not None:
            status = {"status": _change(ModelStatus.TESTING, ModelStatus.ACTIVE)}
            rows.append(
                _entry(
                    "models",
                    plan.model_id,
                    ChangeAction.STATUS_CHANGE,
                    status,
                    "연결 테스트 통과 후 활성화",
                    _actor(plan.created_by, plan.activated_at),
                    plan.activated_at,
                )
            )
        if plan.deactivated_at is not None and plan.replaced_by is not None:
            status = {"status": _change(ModelStatus.ACTIVE, ModelStatus.INACTIVE)}
            reason = f"후속 모델({names[plan.replaced_by]})로 호출 전환 완료"
            rows.append(
                _entry(
                    "models",
                    plan.model_id,
                    ChangeAction.STATUS_CHANGE,
                    status,
                    reason,
                    _actor(plan.created_by, plan.deactivated_at),
                    plan.deactivated_at,
                )
            )
    return rows


def _customer_entries() -> list[Row]:
    rows: list[Row] = []
    for customer in CUSTOMERS:
        if customer.usage_from > PERIOD_START:
            changes = {"is_active": _change(None, True)}
            rows.append(
                _entry(
                    "customers",
                    customer.customer_id,
                    ChangeAction.CREATE,
                    changes,
                    "신규 계약",
                    ADMIN,
                    customer.usage_from - CONTRACT_LEAD,
                )
            )
        if customer.usage_until is not None:
            changes = {"is_active": _change(True, False)}
            rows.append(
                _entry(
                    "customers",
                    customer.customer_id,
                    ChangeAction.DEACTIVATE,
                    changes,
                    "계약 종료",
                    ADMIN,
                    customer.usage_until,
                )
            )
            for key in (k for k in KEYS if k.customer_id == customer.customer_id):
                changes = {"status": _change(KeyStatus.ACTIVE, KeyStatus.INACTIVE)}
                rows.append(
                    _entry(
                        "api_keys",
                        key.key_id,
                        ChangeAction.STATUS_CHANGE,
                        changes,
                        "고객 계약 종료로 Key 사용 중지",
                        ADMIN,
                        customer.usage_until,
                    )
                )
    return rows


def _budget_entries() -> list[Row]:
    budgets = {b.budget_id: b for b in BUDGETS}
    # 1→2: 로웰린 스튜디오 예산 상향, 7→8: AI PDP 개발 프로젝트 예산 변경
    fashion_old, fashion_new = budgets[1], budgets[2]
    project_old, project_new = budgets[7], budgets[8]
    return [
        _entry("budgets", fashion_old.budget_id, ChangeAction.UPDATE,
               {"effective_to_month": _change(None, OCTOBER.isoformat())},
               "10월 예산 초과로 11월부터 예산 상향 (새 예산으로 이어감)", ADMIN, kst(11, 2, 10, 30)),
        _entry("budgets", fashion_new.budget_id, ChangeAction.CREATE,
               {"monthly_amount_usd": _change(None, str(fashion_new.monthly_amount_usd))},
               "11월부터 적용할 예산", ADMIN, kst(11, 2, 10, 31)),
        _entry("budgets", project_old.budget_id, ChangeAction.UPDATE,
               {"effective_to_month": _change(None, SEPTEMBER.isoformat())},
               "구독료 포함 사용률이 9월까지 주의 단계라 10월부터 예산 상향", 2, kst(9, 30, 18)),
        _entry("budgets", project_new.budget_id, ChangeAction.CREATE,
               {"monthly_amount_usd": _change(None, str(project_new.monthly_amount_usd))},
               "10월부터 적용할 예산", 2, kst(9, 30, 18, 1)),
    ]  # fmt: skip


def _other_entries() -> list[Row]:
    member = next(u for u in USERS if not u.is_active)
    scenario = by_code("DATA_SUMMARY")
    rows = []
    if member.deactivated_at is not None:
        rows.append(
            _entry(
                "users",
                member.user_id,
                ChangeAction.DEACTIVATE,
                {"is_active": _change(True, False)},
                "퇴사로 계정 비활성화",
                ADMIN,
                member.deactivated_at,
            )
        )
    changes = {
        "prompt_template": _change(
            DATA_SUMMARY_PROMPT_BEFORE_CHANGE, scenario.prompt_template
        ),
        "default_json_schema": _change(None, scenario.default_json_schema),
    }
    rows.append(
        _entry(
            "test_scenarios",
            scenario.scenario_id,
            ChangeAction.UPDATE,
            changes,
            "요약 결과를 구조화해 모델별로 비교하도록 조건 추가",
            ADMIN,
            CHANGED_AT,
        )
    )
    return rows


def change_log_rows() -> list[Row]:
    entries = (
        _model_entries() + _customer_entries() + _budget_entries() + _other_entries()
    )
    entries.sort(key=lambda row: row["changed_at"])
    return [{"log_id": number, **row} for number, row in enumerate(entries, start=1)]

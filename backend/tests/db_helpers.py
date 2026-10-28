"""DB 테스트 도우미.

- Factory: 테이블마다 "제약을 모두 만족하는 최소한의 행"을 넣는다. 부모 행(예: 호출 → Key·프로젝트·서비스)은
  값을 넘기지 않으면 자동으로 만들고, 값을 넘기면(None 포함) 그 값을 그대로 쓴다.
- expect_rejected: DB가 그 변경을 거절하는지, 어떤 제약이 거절했는지 확인한다.

ORM이 아니라 SQL로 넣는 이유: 테스트 대상이 DB 제약 자체라서, 모델 코드 구조와 상관없이 검증하기 위해서다.
"""

import itertools
import uuid
from collections.abc import Awaitable, Collection
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from psycopg.types.json import Jsonb
from sqlalchemy import RowMapping, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

# 테스트 데이터의 기준 시각과 기준 월
T0 = datetime(2026, 10, 1, tzinfo=UTC)
MONTH0 = date(2026, 10, 1)
# 만료 검사에 걸리지 않을 먼 미래
FAR_FUTURE = datetime(2100, 1, 1, tzinfo=UTC)
SHA256_HEX_LENGTH = 64


class Factory:
    """테스트 행 생성기. 메서드는 넣은 행 전체(RETURNING *)를 돌려준다."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # 고유값(코드, 이메일 등)이 겹치지 않게 붙이는 일련번호
        self._sequence = itertools.count(1)

    def _next(self) -> int:
        return next(self._sequence)

    async def insert(self, table: str, values: dict[str, Any]) -> RowMapping:
        """한 행을 넣고 그 행을 돌려준다. dict 값은 JSONB로 넣는다."""
        columns = ", ".join(values)
        placeholders = ", ".join(f":{column}" for column in values)
        params = {
            column: Jsonb(value) if isinstance(value, dict) else value
            for column, value in values.items()
        }
        result = await self.session.execute(
            text(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *"
            ),
            params,
        )
        return result.mappings().one()

    # 4. 기준정보

    async def customer(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "customers", {"customer_code": f"CUST-{n}", "name": f"고객 {n}", **values}
        )

    async def project(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "projects",
            {
                "project_code": f"PRJ-{n}",
                "name": f"프로젝트 {n}",
                "project_type": "INTERNAL_DEV",
                **values,
            },
        )

    async def user(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "users",
            {
                "user_code": f"USER-{n}",
                "name": f"관리자 {n}",
                "email": f"admin{n}@example.test",
                "password_hash": "not-a-real-hash",
                **values,
            },
        )

    async def service(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "services",
            {
                "service_code": f"SVC-{n}",
                "name": f"서비스 {n}",
                "service_type": "INTERNAL",
                **values,
            },
        )

    async def api_key(self, **values: Any) -> RowMapping:
        """기본은 프로젝트 Key. owner_type에 맞는 고객·프로젝트를 자동으로 만든다."""
        n = self._next()
        owner_type = values.setdefault("owner_type", "PROJECT")
        if owner_type == "PROJECT" and "project_id" not in values:
            values["project_id"] = (await self.project())["project_id"]
        if owner_type == "CUSTOMER" and "customer_id" not in values:
            values["customer_id"] = (await self.customer())["customer_id"]
        return await self.insert(
            "api_keys", {"display_name": f"Key {n}", "environment": "DEV", **values}
        )

    async def user_session(self, **values: Any) -> RowMapping:
        n = self._next()
        if "user_id" not in values:
            values["user_id"] = (await self.user())["user_id"]
        return await self.insert(
            "user_sessions",
            {
                "token_hash": f"{n:0{SHA256_HEX_LENGTH}x}",
                "expires_at": FAR_FUTURE,
                **values,
            },
        )

    # 5. 모델

    async def model(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "models",
            {
                "openrouter_model_id": f"vendor/model-{n}",
                "provider": "vendor",
                "display_name": f"모델 {n}",
                **values,
            },
        )

    async def model_price(self, **values: Any) -> RowMapping:
        """기본은 가격이 알려진(KNOWN) 현재 유효 가격."""
        if "model_id" not in values:
            values["model_id"] = (await self.model())["model_id"]
        return await self.insert(
            "model_prices",
            {
                "price_status": "KNOWN",
                "input_price_per_token": Decimal("0.000001"),
                "output_price_per_token": Decimal("0.000002"),
                "source": "MANUAL",
                "effective_from": T0,
                "checked_at": T0,
                **values,
            },
        )

    # 6~7. 호출 이력과 시뮬레이션

    async def task(self, **values: Any) -> RowMapping:
        """기본은 내부 개발 작업. 고객 서비스가 아니면 프로젝트를 자동으로 붙인다."""
        origin = values.setdefault("usage_origin", "INTERNAL_DEVELOPMENT")
        if "service_id" not in values:
            values["service_id"] = (await self.service())["service_id"]
        if origin != "CUSTOMER_SERVICE" and "project_id" not in values:
            values["project_id"] = (await self.project())["project_id"]
        return await self.insert(
            "tasks",
            {
                "task_id": uuid.uuid4(),
                "task_type": "generation",
                "data_source": "MOCK",
                **values,
            },
        )

    async def scenario(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "test_scenarios",
            {
                "scenario_code": f"SCN-{n}",
                "name": f"시나리오 {n}",
                "input_type": "TEXT",
                "prompt_template": "요약해 주세요",
                **values,
            },
        )

    async def simulation_run(self, **values: Any) -> RowMapping:
        """기본은 모델 2개짜리 직접 입력(CUSTOM) 실행."""
        test_type = values.setdefault("test_type", "CUSTOM")
        if test_type == "SCENARIO" and "scenario_id" not in values:
            values["scenario_id"] = (await self.scenario())["scenario_id"]
        if "project_id" not in values:
            values["project_id"] = (await self.project())["project_id"]
        if "key_id" not in values:
            values["key_id"] = (await self.api_key())["key_id"]
        if "executed_by" not in values:
            values["executed_by"] = (await self.user())["user_id"]
        return await self.insert(
            "simulation_runs",
            {
                "simulation_id": uuid.uuid4(),
                "prompt_text": "요약해 주세요",
                "execution_config": {},
                "routing_policy": {},
                "input_hash": "0" * SHA256_HEX_LENGTH,
                "model_count": 2,
                "requested_at": T0,
                "data_source": "MOCK",
                **values,
            },
        )

    async def ai_request(self, **values: Any) -> RowMapping:
        """기본은 내부 개발 호출(PENDING, 비용 미확인). usage_origin에 맞는 귀속 값을 자동으로 채운다."""
        origin = values.setdefault("usage_origin", "INTERNAL_DEVELOPMENT")
        if "key_id" not in values:
            values["key_id"] = (await self.api_key())["key_id"]
        if "service_id" not in values:
            values["service_id"] = (await self.service())["service_id"]
        if origin != "CUSTOMER_SERVICE" and "project_id" not in values:
            values["project_id"] = (await self.project())["project_id"]
        if origin in ("SIMULATION", "SYSTEM_TEST") and "executed_by" not in values:
            values["executed_by"] = (await self.user())["user_id"]
        if origin == "SIMULATION" and "simulation_id" not in values:
            values["simulation_id"] = (await self.simulation_run())["simulation_id"]
        return await self.insert(
            "ai_requests",
            {
                "request_id": uuid.uuid4(),
                "call_purpose": "GENERATION",
                "requested_model": "vendor/model",
                "requested_at": T0,
                "data_source": "MOCK",
                **values,
            },
        )

    async def ai_request_payload(self, **values: Any) -> RowMapping:
        if "request_id" not in values:
            values["request_id"] = (await self.ai_request())["request_id"]
        return await self.insert("ai_request_payloads", values)

    async def input_asset(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "input_assets",
            {
                "asset_id": uuid.uuid4(),
                "storage_path": f"uploads/{n}.png",
                "sha256": "0" * SHA256_HEX_LENGTH,
                "mime_type": "image/png",
                "file_size_bytes": 1,
                **values,
            },
        )

    async def cost_adjustment(self, **values: Any) -> RowMapping:
        if "request_id" not in values:
            values["request_id"] = (await self.ai_request())["request_id"]
        return await self.insert(
            "cost_adjustments",
            {
                "old_cost_status": "UNKNOWN",
                "new_cost_status": "CONFIRMED",
                "reason": "OpenRouter 대조",
                **values,
            },
        )

    async def simulation_run_asset(self, **values: Any) -> RowMapping:
        if "simulation_id" not in values:
            values["simulation_id"] = (await self.simulation_run())["simulation_id"]
        if "asset_id" not in values:
            values["asset_id"] = (await self.input_asset())["asset_id"]
        return await self.insert("simulation_run_assets", {"sort_order": 1, **values})

    async def simulation_result(self, **values: Any) -> RowMapping:
        """기본은 1번 칸의 최종 결과. 같은 실행에 속한 시뮬레이션 호출을 자동으로 만든다."""
        n = self._next()
        if "simulation_id" not in values:
            values["simulation_id"] = (await self.simulation_run())["simulation_id"]
        if "request_id" not in values:
            request = await self.ai_request(
                usage_origin="SIMULATION", simulation_id=values["simulation_id"]
            )
            values["request_id"] = request["request_id"]
        if "model_id" not in values:
            values["model_id"] = (await self.model())["model_id"]
        return await self.insert(
            "simulation_results",
            {
                "slot_no": 1,
                "execution_provider": "provider-a",
                "model_status_at_run": "ACTIVE",
                "model_display_name_at_run": f"모델 {n}",
                **values,
            },
        )

    # 8. 예산·구독료

    async def budget(self, **values: Any) -> RowMapping:
        """기본은 새 프로젝트의 월 예산(2026-10부터 무기한). 대상이 매번 달라 기간 겹침에 걸리지 않는다."""
        scope_type = values.setdefault("scope_type", "PROJECT")
        if scope_type == "PROJECT" and "project_id" not in values:
            values["project_id"] = (await self.project())["project_id"]
        if scope_type == "CUSTOMER" and "customer_id" not in values:
            values["customer_id"] = (await self.customer())["customer_id"]
        return await self.insert(
            "budgets",
            {
                "monthly_amount_usd": Decimal(100),
                "effective_from_month": MONTH0,
                **values,
            },
        )

    async def subscription_cost(self, **values: Any) -> RowMapping:
        n = self._next()
        return await self.insert(
            "subscription_costs",
            {
                "subscription_reference": f"SUB-{n}",
                "tool_name": f"도구 {n}",
                "applied_month": MONTH0,
                "amount": Decimal(10),
                **values,
            },
        )

    # 9. 대조·감사

    async def key_usage_snapshot(self, **values: Any) -> RowMapping:
        if "key_id" not in values:
            values["key_id"] = (await self.api_key())["key_id"]
        return await self.insert("key_usage_snapshots", {"captured_at": T0, **values})

    async def usage_reconciliation(self, **values: Any) -> RowMapping:
        """기본은 비교 불가(UNCOMPARABLE). COMPARABLE이면 외부 사용량·차액을 0으로 채운다."""
        comparability = values.setdefault("comparability", "UNCOMPARABLE")
        if comparability == "COMPARABLE":
            values.setdefault("external_usage_usd", Decimal(0))
            values.setdefault("difference_usd", Decimal(0))
        if "key_id" not in values:
            values["key_id"] = (await self.api_key())["key_id"]
        return await self.insert(
            "usage_reconciliations",
            {
                "period_start": T0,
                "period_end": T0 + timedelta(days=1),
                "patron_confirmed_usd": Decimal(0),
                "patron_estimated_usd": Decimal(0),
                "patron_unknown_count": 0,
                **values,
            },
        )

    async def change_log(self, **values: Any) -> RowMapping:
        return await self.insert(
            "change_logs",
            {
                "entity_type": "api_keys",
                "entity_id": "1",
                "action": "UPDATE",
                "changes": {},
                **values,
            },
        )


async def expect_rejected(
    session: AsyncSession,
    operation: Awaitable[object],
    *,
    constraint: str | Collection[str] | None = None,
    sqlstate: str | None = None,
) -> None:
    """operation이 DB에서 거절되는지 확인한다.

    savepoint 안에서 실행하므로 거절되어도 테스트의 나머지 작업은 계속할 수 있다.
    constraint: 거절한 제약 이름(여러 제약이 동시에 걸릴 수 있으면 후보 묶음).
    sqlstate: 제약 이름이 없는 오류(예: 생성 컬럼에 값 넣기)의 PostgreSQL 오류 코드.
    """
    with pytest.raises(DBAPIError) as caught:
        async with session.begin_nested():
            await operation
    error = caught.value.orig
    if constraint is not None:
        expected = {constraint} if isinstance(constraint, str) else set(constraint)
        assert error.diag.constraint_name in expected
    if sqlstate is not None:
        assert error.sqlstate == sqlstate

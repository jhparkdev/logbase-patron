"""app/models.py와 첫 마이그레이션이 만든 DB 제약 테스트 (설계서 v0.6 기준).

각 제약은 "허용되어야 하는 경우"와 "거절되어야 하는 경우"를 함께 검사한다.
거절될 때는 어떤 제약이 거절했는지 이름까지 확인한다. 제약 이름은 설계 SQL과 같아야 한다.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CostSource
from tests.db_helpers import MONTH0, T0, Factory, expect_rejected

# NUMERIC(30,18)에서 0보다 작은 가장 가까운 값
JUST_BELOW_ZERO = Decimal("-0.000000000000000001")
# PostgreSQL 오류 코드: 생성 컬럼(GENERATED ALWAYS)에 값을 직접 넣음
GENERATED_ALWAYS_SQLSTATE = "428C9"
# 어느 값 목록에도 없는 값. CHAR(3) 컬럼(currency)에도 들어가도록 세 글자로 둔다.
INVALID_VALUE = "XXX"
ONE_MICROSECOND = timedelta(microseconds=1)


# ---------------------------------------------------------------------------
# 값 목록 CHECK (status IN (...) 형태): 허용 값은 모두 통과, 목록에 없는 값은 거절
# ---------------------------------------------------------------------------

# (테이블, Factory 메서드, 컬럼, 허용 값, 함께 넣을 값, 같이 걸릴 수 있는 다른 제약)
ALLOWED_VALUES: list[tuple[str, str, str, list[str], dict[str, Any], set[str]]] = [
    (
        "projects",
        "project",
        "project_type",
        ["INTERNAL_DEV", "CUSTOMER_PROJECT", "POC", "TEST"],
        {},
        set(),
    ),
    (
        "services",
        "service",
        "service_type",
        ["CUSTOMER_FACING", "INTERNAL", "PATRON"],
        {},
        set(),
    ),
    (
        "api_keys",
        "api_key",
        "owner_type",
        ["CUSTOMER", "PROJECT"],
        {},
        {"ck_api_keys_owner"},
    ),
    ("api_keys", "api_key", "environment", ["DEV", "TEST", "PROD"], {}, set()),
    ("api_keys", "api_key", "status", ["ACTIVE", "INACTIVE"], {}, set()),
    (
        "api_keys",
        "api_key",
        "limit_reset_period",
        ["NONE", "DAILY", "WEEKLY", "MONTHLY"],
        {},
        set(),
    ),
    ("models", "model", "status", ["TESTING", "ACTIVE", "INACTIVE"], {}, set()),
    (
        "models",
        "model",
        "last_test_status",
        ["SUCCESS", "FAILED", "TIMEOUT"],
        {},
        set(),
    ),
    ("model_prices", "model_price", "price_status", ["KNOWN", "UNKNOWN"], {}, set()),
    (
        "model_prices",
        "model_price",
        "source",
        ["OPENROUTER_MODELS", "OPENROUTER_ENDPOINTS", "MANUAL"],
        {},
        set(),
    ),
    (
        "tasks",
        "task",
        "usage_origin",
        ["CUSTOMER_SERVICE", "INTERNAL_DEVELOPMENT", "SIMULATION", "SYSTEM_TEST"],
        {"project_id": None},
        set(),
    ),
    ("tasks", "task", "data_source", ["MOCK", "LIVE"], {}, set()),
    (
        "test_scenarios",
        "scenario",
        "input_type",
        ["TEXT", "IMAGE", "TEXT_IMAGE"],
        {},
        set(),
    ),
    (
        "simulation_runs",
        "simulation_run",
        "test_type",
        ["SCENARIO", "CUSTOM"],
        {},
        {"ck_simulation_runs_scenario"},
    ),
    (
        "simulation_runs",
        "simulation_run",
        "status",
        ["PENDING", "RUNNING", "SUCCESS", "PARTIAL_SUCCESS", "FAILED", "CANCELLED"],
        {},
        set(),
    ),
    ("simulation_runs", "simulation_run", "data_source", ["MOCK", "LIVE"], {}, set()),
    (
        "ai_requests",
        "ai_request",
        "usage_origin",
        ["CUSTOMER_SERVICE", "INTERNAL_DEVELOPMENT", "SIMULATION", "SYSTEM_TEST"],
        {},
        set(),
    ),
    (
        "ai_requests",
        "ai_request",
        "call_purpose",
        ["GENERATION", "EVALUATION", "REGENERATION", "EXPERIMENT", "TEST", "OTHER"],
        {},
        set(),
    ),
    (
        "ai_requests",
        "ai_request",
        "error_type",
        [
            "AUTH_ERROR",
            "RATE_LIMIT",
            "TIMEOUT_ERROR",
            "PROVIDER_ERROR",
            "NETWORK_ERROR",
            "INVALID_RESPONSE",
            "UNSUPPORTED_INPUT",
            "UNKNOWN_ERROR",
        ],
        {"status": "FAILED"},
        set(),
    ),
    (
        "ai_requests",
        "ai_request",
        "cost_source",
        [
            "API_RESPONSE",
            "GENERATION_LOOKUP",
            "PRICE_ESTIMATE",
            "MANUAL",
            "MOCK",
            "NO_CHARGE",
        ],
        {
            "status": "FAILED",
            "error_type": "PROVIDER_ERROR",
            "cost_status": "CONFIRMED",
            "cost_usd": Decimal(0),
        },
        set(),
    ),
    ("ai_requests", "ai_request", "data_source", ["MOCK", "LIVE"], {}, set()),
    (
        "cost_adjustments",
        "cost_adjustment",
        "old_cost_status",
        ["CONFIRMED", "ESTIMATED", "UNKNOWN"],
        {},
        set(),
    ),
    (
        "cost_adjustments",
        "cost_adjustment",
        "new_cost_status",
        ["CONFIRMED", "ESTIMATED", "UNKNOWN"],
        {},
        set(),
    ),
    (
        "simulation_results",
        "simulation_result",
        "model_status_at_run",
        ["TESTING", "ACTIVE", "INACTIVE"],
        {},
        set(),
    ),
    (
        "simulation_results",
        "simulation_result",
        "json_parse_status",
        ["PASSED", "FAILED", "NOT_APPLICABLE", "NOT_EXECUTED"],
        {},
        set(),
    ),
    (
        "simulation_results",
        "simulation_result",
        "schema_validation_status",
        ["PASSED", "FAILED", "NOT_APPLICABLE", "NOT_EXECUTED"],
        {},
        set(),
    ),
    (
        "budgets",
        "budget",
        "scope_type",
        ["CUSTOMER", "PROJECT"],
        {},
        {"ck_budgets_scope"},
    ),
    ("subscription_costs", "subscription_cost", "currency", ["USD"], {}, set()),
    (
        "subscription_costs",
        "subscription_cost",
        "status",
        ["ACTIVE", "CANCELLED"],
        {},
        set(),
    ),
    (
        "usage_reconciliations",
        "usage_reconciliation",
        "comparability",
        ["COMPARABLE", "UNCOMPARABLE"],
        {},
        {"ck_usage_reconciliations_comparable"},
    ),
    (
        "usage_reconciliations",
        "usage_reconciliation",
        "status",
        ["OPEN", "REVIEWED"],
        {},
        set(),
    ),
    (
        "change_logs",
        "change_log",
        "action",
        ["CREATE", "UPDATE", "STATUS_CHANGE", "DEACTIVATE"],
        {},
        set(),
    ),
]


@pytest.mark.parametrize(
    ("table", "method", "column", "allowed", "context", "also"),
    ALLOWED_VALUES,
    ids=[f"{row[0]}.{row[2]}" for row in ALLOWED_VALUES],
)
async def test_value_list_check(
    factory: Factory,
    db_session: AsyncSession,
    table: str,
    method: str,
    column: str,
    allowed: list[str],
    context: dict[str, Any],
    also: set[str],
) -> None:
    make = getattr(factory, method)
    for value in allowed:
        await make(**context, **{column: value})

    await expect_rejected(
        db_session,
        make(**context, **{column: INVALID_VALUE}),
        constraint={f"{table}_{column}_check", *also},
    )


# ---------------------------------------------------------------------------
# 최솟값 CHECK (>= 0, > 0 형태): 허용되는 최솟값은 통과, 바로 아래 값은 거절
# ---------------------------------------------------------------------------

# (테이블, Factory 메서드, 컬럼, 허용 최솟값, 거절 값, 함께 넣을 값, 같이 걸릴 수 있는 다른 제약)
LOWER_BOUNDS: list[tuple[str, str, str, Any, Any, dict[str, Any], set[str]]] = [
    ("api_keys", "api_key", "limit_usd", Decimal(0), JUST_BELOW_ZERO, {}, set()),
    ("models", "model", "context_length", 1, 0, {}, set()),
    (
        "model_prices",
        "model_price",
        "input_price_per_token",
        Decimal(0),
        JUST_BELOW_ZERO,
        {},
        set(),
    ),
    (
        "model_prices",
        "model_price",
        "output_price_per_token",
        Decimal(0),
        JUST_BELOW_ZERO,
        {},
        set(),
    ),
    (
        "model_prices",
        "model_price",
        "cache_read_price_per_token",
        Decimal(0),
        JUST_BELOW_ZERO,
        {},
        set(),
    ),
    (
        "model_prices",
        "model_price",
        "cache_write_price_per_token",
        Decimal(0),
        JUST_BELOW_ZERO,
        {},
        set(),
    ),
    ("ai_requests", "ai_request", "attempt_no", 1, 0, {}, {"ck_ai_requests_retry"}),
    ("ai_requests", "ai_request", "latency_ms", 0, -1, {}, set()),
    ("ai_requests", "ai_request", "input_tokens", 0, -1, {}, set()),
    ("ai_requests", "ai_request", "output_tokens", 0, -1, {}, set()),
    ("ai_requests", "ai_request", "cached_tokens", 0, -1, {}, set()),
    ("ai_requests", "ai_request", "cache_write_tokens", 0, -1, {}, set()),
    ("ai_requests", "ai_request", "reasoning_tokens", 0, -1, {}, set()),
    (
        "ai_requests",
        "ai_request",
        "cost_usd",
        Decimal(0),
        JUST_BELOW_ZERO,
        {"cost_status": "CONFIRMED"},
        set(),
    ),
    ("input_assets", "input_asset", "file_size_bytes", 0, -1, {}, set()),
    ("output_assets", "output_asset", "file_size_bytes", 0, -1, {}, set()),
    ("output_assets", "output_asset", "sort_order", 0, -1, {}, set()),
    (
        "budgets",
        "budget",
        "monthly_amount_usd",
        Decimal("0.000000000000000001"),
        Decimal(0),
        {},
        set(),
    ),
    (
        "subscription_costs",
        "subscription_cost",
        "amount",
        Decimal(0),
        Decimal("-0.0001"),
        {},
        set(),
    ),
    (
        "usage_reconciliations",
        "usage_reconciliation",
        "patron_unknown_count",
        0,
        -1,
        {},
        set(),
    ),
]


@pytest.mark.parametrize(
    ("table", "method", "column", "minimum", "below", "context", "also"),
    LOWER_BOUNDS,
    ids=[f"{row[0]}.{row[2]}" for row in LOWER_BOUNDS],
)
async def test_lower_bound_check(
    factory: Factory,
    db_session: AsyncSession,
    table: str,
    method: str,
    column: str,
    minimum: Any,
    below: Any,
    context: dict[str, Any],
    also: set[str],
) -> None:
    make = getattr(factory, method)
    await make(**context, **{column: minimum})

    await expect_rejected(
        db_session,
        make(**context, **{column: below}),
        constraint={f"{table}_{column}_check", *also},
    )


# ---------------------------------------------------------------------------
# 경계값: 바로 전, 정확히 그 값, 바로 후
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model_count", "accepted"), [(1, False), (2, True), (4, True), (5, False)]
)
async def test_simulation_model_count_is_between_2_and_4(
    factory: Factory, db_session: AsyncSession, model_count: int, accepted: bool
) -> None:
    operation = factory.simulation_run(model_count=model_count)
    if accepted:
        await operation
    else:
        await expect_rejected(
            db_session, operation, constraint="simulation_runs_model_count_check"
        )


@pytest.mark.parametrize(
    ("slot_no", "accepted"), [(0, False), (1, True), (4, True), (5, False)]
)
async def test_simulation_result_slot_is_between_1_and_4(
    factory: Factory, db_session: AsyncSession, slot_no: int, accepted: bool
) -> None:
    operation = factory.simulation_result(slot_no=slot_no)
    if accepted:
        await operation
    else:
        await expect_rejected(
            db_session, operation, constraint="simulation_results_slot_no_check"
        )


@pytest.mark.parametrize(
    ("percent", "accepted"),
    [
        (Decimal("-0.01"), False),
        (Decimal(0), True),
        (Decimal(100), True),
        (Decimal("100.01"), False),
    ],
)
async def test_budget_warning_threshold_is_between_0_and_100(
    factory: Factory, db_session: AsyncSession, percent: Decimal, accepted: bool
) -> None:
    operation = factory.budget(warning_threshold_pct=percent)
    if accepted:
        await operation
    else:
        await expect_rejected(
            db_session, operation, constraint="budgets_warning_threshold_pct_check"
        )


@pytest.mark.parametrize(
    ("method", "column", "constraint"),
    [
        ("budget", "effective_from_month", "budgets_effective_from_month_check"),
        ("budget", "effective_to_month", "budgets_effective_to_month_check"),
        (
            "subscription_cost",
            "applied_month",
            "subscription_costs_applied_month_check",
        ),
    ],
)
async def test_month_columns_must_be_first_day(
    factory: Factory,
    db_session: AsyncSession,
    method: str,
    column: str,
    constraint: str,
) -> None:
    make = getattr(factory, method)
    await make(**{column: date(2026, 11, 1)})

    await expect_rejected(
        db_session, make(**{column: date(2026, 11, 2)}), constraint=constraint
    )


async def test_session_token_hash_is_lowercase_sha256_hex(
    factory: Factory, db_session: AsyncSession
) -> None:
    await factory.user_session(token_hash="a" * 64)

    for bad_hash in ("A" * 64, "a" * 63, "g" * 64):
        await expect_rejected(
            db_session,
            factory.user_session(token_hash=bad_hash),
            constraint="user_sessions_token_hash_check",
        )


async def test_session_must_expire_after_creation(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_user_sessions_expiry: 만료 시각이 발급 시각과 같으면 거절, 1마이크로초라도 뒤면 허용."""
    await factory.user_session(created_at=T0, expires_at=T0 + ONE_MICROSECOND)

    await expect_rejected(
        db_session,
        factory.user_session(created_at=T0, expires_at=T0),
        constraint="ck_user_sessions_expiry",
    )


# ---------------------------------------------------------------------------
# 조건부 CHECK (ck_…)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "type_column", "name"),
    [
        ("api_key", "owner_type", "ck_api_keys_owner"),
        ("budget", "scope_type", "ck_budgets_scope"),
    ],
)
async def test_owner_matches_type(
    factory: Factory, db_session: AsyncSession, method: str, type_column: str, name: str
) -> None:
    """Key와 예산은 종류(고객/프로젝트)에 맞는 대상 하나만 가진다."""
    make = getattr(factory, method)
    customer_id = (await factory.customer())["customer_id"]
    project_id = (await factory.project())["project_id"]

    await make(
        **{type_column: "CUSTOMER", "customer_id": customer_id, "project_id": None}
    )
    await make(
        **{type_column: "PROJECT", "project_id": project_id, "customer_id": None}
    )

    for customer, project in [
        (None, project_id),
        (customer_id, project_id),
        (None, None),
    ]:
        await expect_rejected(
            db_session,
            make(
                **{
                    type_column: "CUSTOMER",
                    "customer_id": customer,
                    "project_id": project,
                }
            ),
            constraint=name,
        )


async def test_known_price_requires_input_and_output_price(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_model_prices_known: 가격을 안다(KNOWN)면 입력·출력 단가가 모두 있어야 한다."""
    await factory.model_price(
        price_status="UNKNOWN", input_price_per_token=None, output_price_per_token=None
    )

    for missing in ("input_price_per_token", "output_price_per_token"):
        await expect_rejected(
            db_session,
            factory.model_price(price_status="KNOWN", **{missing: None}),
            constraint="ck_model_prices_known",
        )


@pytest.mark.parametrize(
    ("method", "start_column", "end_column", "name", "start"),
    [
        ("model_price", "effective_from", "effective_to", "ck_model_prices_period", T0),
        (
            "usage_reconciliation",
            "period_start",
            "period_end",
            "ck_usage_reconciliations_period",
            T0,
        ),
        (
            "budget",
            "effective_from_month",
            "effective_to_month",
            "ck_budgets_period",
            MONTH0,
        ),
    ],
)
async def test_period_end_is_not_before_start(
    factory: Factory,
    db_session: AsyncSession,
    method: str,
    start_column: str,
    end_column: str,
    name: str,
    start: Any,
) -> None:
    """기간의 끝이 시작보다 앞서면 거절한다.

    가격·대조는 끝 > 시작이어야 하고(같으면 거절), 예산은 끝 월 >= 시작 월이다(같은 달 허용).
    """
    make = getattr(factory, method)
    if isinstance(start, date) and not isinstance(start, datetime):
        await make(**{start_column: start, end_column: start})
        before = date(start.year, start.month - 1, 1)
        await expect_rejected(
            db_session,
            make(**{start_column: start, end_column: before}),
            constraint=name,
        )
    else:
        await make(**{start_column: start, end_column: start + ONE_MICROSECOND})
        await expect_rejected(
            db_session,
            make(**{start_column: start, end_column: start}),
            constraint=name,
        )


@pytest.mark.parametrize(
    ("method", "start_column", "end_column", "name"),
    [
        ("task", "started_at", "completed_at", "ck_tasks_period"),
        ("simulation_run", "requested_at", "completed_at", "ck_simulation_runs_period"),
        ("ai_request", "requested_at", "completed_at", "ck_ai_requests_period"),
    ],
)
async def test_completion_is_not_before_start(
    factory: Factory,
    db_session: AsyncSession,
    method: str,
    start_column: str,
    end_column: str,
    name: str,
) -> None:
    """완료 시각은 시작(요청) 시각과 같거나 뒤여야 한다."""
    make = getattr(factory, method)
    await make(**{start_column: T0, end_column: T0})

    await expect_rejected(
        db_session,
        make(**{start_column: T0, end_column: T0 - ONE_MICROSECOND}),
        constraint=name,
    )


async def test_task_owner_matches_origin(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_tasks_origin_owner·single_owner: 고객 작업에는 프로젝트를, 내부 작업에는 고객을 붙일 수 없다."""
    customer_id = (await factory.customer())["customer_id"]
    project_id = (await factory.project())["project_id"]

    await factory.task(
        usage_origin="CUSTOMER_SERVICE", customer_id=customer_id, project_id=None
    )
    await factory.task(
        usage_origin="CUSTOMER_SERVICE", customer_id=None, project_id=None
    )
    await factory.task(usage_origin="INTERNAL_DEVELOPMENT", project_id=project_id)
    await factory.task(usage_origin="INTERNAL_DEVELOPMENT", project_id=None)

    owner_constraints = {"ck_tasks_origin_owner", "ck_tasks_single_owner"}
    await expect_rejected(
        db_session,
        factory.task(usage_origin="CUSTOMER_SERVICE", project_id=project_id),
        constraint=owner_constraints,
    )
    await expect_rejected(
        db_session,
        factory.task(
            usage_origin="INTERNAL_DEVELOPMENT",
            customer_id=customer_id,
            project_id=None,
        ),
        constraint="ck_tasks_origin_owner",
    )
    await expect_rejected(
        db_session,
        factory.task(
            usage_origin="CUSTOMER_SERVICE",
            customer_id=customer_id,
            project_id=project_id,
        ),
        constraint=owner_constraints,
    )


async def test_simulation_scenario_matches_test_type(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_simulation_runs_scenario: 시나리오 실행에만 시나리오를 붙인다."""
    scenario_id = (await factory.scenario())["scenario_id"]
    await factory.simulation_run(test_type="SCENARIO", scenario_id=scenario_id)
    await factory.simulation_run(test_type="CUSTOM", scenario_id=None)

    await expect_rejected(
        db_session,
        factory.simulation_run(test_type="SCENARIO", scenario_id=None),
        constraint="ck_simulation_runs_scenario",
    )
    await expect_rejected(
        db_session,
        factory.simulation_run(test_type="CUSTOM", scenario_id=scenario_id),
        constraint="ck_simulation_runs_scenario",
    )


async def test_rerun_cannot_point_to_itself(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_simulation_runs_not_self: 재실행은 새 ID로 만들고, 자기 자신을 원본으로 가리킬 수 없다."""
    original = await factory.simulation_run()
    await factory.simulation_run(rerun_of_simulation_id=original["simulation_id"])

    own_id = uuid.uuid4()
    await expect_rejected(
        db_session,
        factory.simulation_run(simulation_id=own_id, rerun_of_simulation_id=own_id),
        constraint="ck_simulation_runs_not_self",
    )


async def test_customer_usage_is_not_mixed_with_internal_cost(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_origin_owner (CLAUDE.md CRITICAL): 고객 호출과 내부 비용을 섞지 않는다.

    고객 호출에는 프로젝트를 붙일 수 없고, 내부 호출은 프로젝트가 필수이며 고객을 붙일 수 없다.
    고객을 알 수 없는 고객 호출은 미분류(customer_id NULL)로 허용한다.
    """
    customer_id = (await factory.customer())["customer_id"]
    project_id = (await factory.project())["project_id"]

    await factory.ai_request(usage_origin="CUSTOMER_SERVICE", customer_id=customer_id)
    await factory.ai_request(usage_origin="CUSTOMER_SERVICE", customer_id=None)
    await factory.ai_request(usage_origin="INTERNAL_DEVELOPMENT", project_id=project_id)

    owner_constraints = {"ck_ai_requests_origin_owner", "ck_ai_requests_single_owner"}
    await expect_rejected(
        db_session,
        factory.ai_request(usage_origin="CUSTOMER_SERVICE", project_id=project_id),
        constraint=owner_constraints,
    )
    await expect_rejected(
        db_session,
        factory.ai_request(usage_origin="INTERNAL_DEVELOPMENT", project_id=None),
        constraint="ck_ai_requests_origin_owner",
    )
    await expect_rejected(
        db_session,
        factory.ai_request(
            usage_origin="INTERNAL_DEVELOPMENT",
            customer_id=customer_id,
            project_id=project_id,
        ),
        constraint=owner_constraints,
    )


async def test_simulation_request_requires_simulation_id(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_simulation: 시뮬레이션 호출은 실행 ID가 필수다."""
    await expect_rejected(
        db_session,
        factory.ai_request(usage_origin="SIMULATION", simulation_id=None),
        constraint="ck_ai_requests_simulation",
    )


async def test_executor_is_recorded_only_for_simulation_and_system_test(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_executed_by: 시뮬레이션·연결 테스트만 실행자를 기록하고, 그 밖의 호출은 기록하지 않는다."""
    user_id = (await factory.user())["user_id"]
    await factory.ai_request(usage_origin="SYSTEM_TEST", executed_by=user_id)

    for origin in ("SIMULATION", "SYSTEM_TEST"):
        await expect_rejected(
            db_session,
            factory.ai_request(usage_origin=origin, executed_by=None),
            constraint="ck_ai_requests_executed_by",
        )
    for origin in ("CUSTOMER_SERVICE", "INTERNAL_DEVELOPMENT"):
        await expect_rejected(
            db_session,
            factory.ai_request(usage_origin=origin, executed_by=user_id),
            constraint="ck_ai_requests_executed_by",
        )


async def test_retry_requires_parent_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_retry: 첫 시도는 부모가 없고, 재시도(2회차 이상)는 부모 호출이 있어야 한다."""
    first = await factory.ai_request(attempt_no=1)
    await factory.ai_request(attempt_no=2, parent_request_id=first["request_id"])

    await expect_rejected(
        db_session,
        factory.ai_request(attempt_no=2, parent_request_id=None),
        constraint="ck_ai_requests_retry",
    )
    await expect_rejected(
        db_session,
        factory.ai_request(attempt_no=1, parent_request_id=first["request_id"]),
        constraint="ck_ai_requests_retry",
    )


async def test_unknown_cost_is_null_not_zero(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_cost_unknown (CLAUDE.md CRITICAL): 비용 미확인 ⇔ cost_usd IS NULL. 0으로 기록하지 않는다."""
    await factory.ai_request(cost_status="UNKNOWN", cost_usd=None)
    await factory.ai_request(cost_status="CONFIRMED", cost_usd=Decimal(0))

    await expect_rejected(
        db_session,
        factory.ai_request(cost_status="UNKNOWN", cost_usd=Decimal(0)),
        constraint="ck_ai_requests_cost_unknown",
    )
    await expect_rejected(
        db_session,
        factory.ai_request(cost_status="CONFIRMED", cost_usd=None),
        constraint="ck_ai_requests_cost_unknown",
    )


def test_cost_source_exposes_no_charge() -> None:
    assert CostSource.NO_CHARGE.value == "NO_CHARGE"


@pytest.mark.parametrize(
    ("status", "error_type", "cost_status", "cost_usd", "accepted"),
    [
        ("FAILED", "PROVIDER_ERROR", "CONFIRMED", Decimal(0), True),
        ("FAILED", "PROVIDER_ERROR", "CONFIRMED", -JUST_BELOW_ZERO, False),
        ("FAILED", "PROVIDER_ERROR", "UNKNOWN", None, False),
        ("FAILED", "PROVIDER_ERROR", "ESTIMATED", Decimal(0), False),
        ("SUCCESS", None, "CONFIRMED", Decimal(0), False),
        ("PENDING", None, "CONFIRMED", Decimal(0), False),
        ("RUNNING", None, "CONFIRMED", Decimal(0), False),
        ("TIMEOUT", "TIMEOUT_ERROR", "CONFIRMED", Decimal(0), False),
        ("CANCELLED", None, "CONFIRMED", Decimal(0), False),
    ],
)
async def test_no_charge_requires_failed_confirmed_zero_cost(
    factory: Factory,
    db_session: AsyncSession,
    status: str,
    error_type: str | None,
    cost_status: str,
    cost_usd: Decimal | None,
    accepted: bool,
) -> None:
    """청구 없음의 근거는 실패·확정·0원일 때만 쓸 수 있다."""
    price_id = (
        (await factory.model_price())["price_id"]
        if cost_status == "ESTIMATED"
        else None
    )
    operation = factory.ai_request(
        status=status,
        error_type=error_type,
        cost_status=cost_status,
        cost_usd=cost_usd,
        cost_source="NO_CHARGE",
        price_id=price_id,
    )
    if accepted:
        request = await operation
        assert request["cost_source"] == "NO_CHARGE"
        assert request["cost_usd"] == Decimal(0)
    else:
        await expect_rejected(
            db_session, operation, constraint="ck_ai_requests_no_charge"
        )


@pytest.mark.parametrize(
    ("status", "error_type"),
    [("TIMEOUT", "TIMEOUT_ERROR"), ("FAILED", "NETWORK_ERROR"), ("CANCELLED", None)],
)
async def test_uncertain_failures_can_keep_unknown_cost(
    factory: Factory, status: str, error_type: str | None
) -> None:
    """응답이 없는 실패는 나중에 청구될 수 있으므로 비용 미확인을 유지할 수 있다."""
    request = await factory.ai_request(
        status=status,
        error_type=error_type,
        cost_status="UNKNOWN",
        cost_usd=None,
        cost_source=None,
    )
    assert request["cost_status"] == "UNKNOWN"
    assert request["cost_usd"] is None


async def test_estimated_cost_requires_price(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_cost_estimated: 추정 비용에는 근거가 된 가격이 있어야 한다."""
    price_id = (await factory.model_price())["price_id"]
    await factory.ai_request(
        cost_status="ESTIMATED", cost_usd=Decimal("0.1"), price_id=price_id
    )

    await expect_rejected(
        db_session,
        factory.ai_request(
            cost_status="ESTIMATED", cost_usd=Decimal("0.1"), price_id=None
        ),
        constraint="ck_ai_requests_cost_estimated",
    )


async def test_error_type_matches_status(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_ai_requests_error: 성공에는 오류 종류가 없고, 실패·시간 초과에는 반드시 있다."""
    await factory.ai_request(status="SUCCESS", error_type=None)
    for status in ("FAILED", "TIMEOUT"):
        await factory.ai_request(status=status, error_type="PROVIDER_ERROR")
    for status in ("PENDING", "RUNNING", "CANCELLED"):
        await factory.ai_request(status=status, error_type=None)
        await factory.ai_request(status=status, error_type="NETWORK_ERROR")

    await expect_rejected(
        db_session,
        factory.ai_request(status="SUCCESS", error_type="PROVIDER_ERROR"),
        constraint="ck_ai_requests_error",
    )
    for status in ("FAILED", "TIMEOUT"):
        await expect_rejected(
            db_session,
            factory.ai_request(status=status, error_type=None),
            constraint="ck_ai_requests_error",
        )
    await expect_rejected(
        db_session,
        factory.ai_request(status="NOT_A_STATUS"),
        constraint={"ai_requests_status_check", "ck_ai_requests_error"},
    )


@pytest.mark.parametrize(
    ("detail", "total"),
    [("cached_tokens", "input_tokens"), ("reasoning_tokens", "output_tokens")],
)
async def test_detail_tokens_do_not_exceed_total(
    factory: Factory, db_session: AsyncSession, detail: str, total: str
) -> None:
    """ck_ai_requests_token_breakdown: 세부 Token(캐시·추론)은 상위 Token에 포함되므로 더 클 수 없다."""
    await factory.ai_request(**{total: 10, detail: 10})
    await factory.ai_request(**{total: None, detail: 10})

    await expect_rejected(
        db_session,
        factory.ai_request(**{total: 10, detail: 11}),
        constraint="ck_ai_requests_token_breakdown",
    )


async def test_reconciliation_difference_only_when_comparable(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ck_usage_reconciliations_comparable: 비교 가능할 때만 외부 사용량과 차액이 있다."""
    await factory.usage_reconciliation(
        comparability="COMPARABLE",
        external_usage_usd=Decimal(1),
        difference_usd=Decimal("0.5"),
    )
    await factory.usage_reconciliation(
        comparability="UNCOMPARABLE", external_usage_usd=None, difference_usd=None
    )

    for external, difference in [(None, Decimal(0)), (Decimal(1), None)]:
        await expect_rejected(
            db_session,
            factory.usage_reconciliation(
                comparability="COMPARABLE",
                external_usage_usd=external,
                difference_usd=difference,
            ),
            constraint="ck_usage_reconciliations_comparable",
        )
    await expect_rejected(
        db_session,
        factory.usage_reconciliation(
            comparability="UNCOMPARABLE",
            external_usage_usd=Decimal(1),
            difference_usd=Decimal(0),
        ),
        constraint="ck_usage_reconciliations_comparable",
    )


# ---------------------------------------------------------------------------
# 고유·부분 고유 인덱스, 기간 겹침(EXCLUDE), 복합 외래키
# ---------------------------------------------------------------------------


async def test_one_current_price_per_model_and_provider(
    factory: Factory, db_session: AsyncSession
) -> None:
    """uq_model_prices_current: 같은 모델·실행 Provider의 현재 유효 가격은 하나다.

    실행 Provider가 NULL(모델 대표가)인 경우도 중복으로 본다(NULLS NOT DISTINCT).
    """
    model_id = (await factory.model())["model_id"]
    await factory.model_price(
        model_id=model_id, execution_provider=None, effective_to=T0 + timedelta(days=1)
    )
    await factory.model_price(model_id=model_id, execution_provider=None)
    await factory.model_price(model_id=model_id, execution_provider="provider-a")

    for provider in (None, "provider-a"):
        await expect_rejected(
            db_session,
            factory.model_price(model_id=model_id, execution_provider=provider),
            constraint="uq_model_prices_current",
        )


async def test_one_final_result_per_slot(
    factory: Factory, db_session: AsyncSession
) -> None:
    """uq_sim_results_slot: 한 실행의 한 칸에는 최종 결과가 하나다(이전 시도는 여러 개 가능)."""
    simulation_id = (await factory.simulation_run())["simulation_id"]
    await factory.simulation_result(
        simulation_id=simulation_id, slot_no=1, is_final_attempt=False
    )
    await factory.simulation_result(
        simulation_id=simulation_id, slot_no=1, is_final_attempt=True
    )

    await expect_rejected(
        db_session,
        factory.simulation_result(
            simulation_id=simulation_id, slot_no=1, is_final_attempt=True
        ),
        constraint="uq_sim_results_slot",
    )


async def test_same_model_and_provider_cannot_repeat_the_same_settings(
    factory: Factory, db_session: AsyncSession
) -> None:
    """같은 모델·Provider·적용 설정의 최종 결과만 중복으로 본다."""
    simulation_id = (await factory.simulation_run())["simulation_id"]
    model_id = (await factory.model())["model_id"]
    await factory.simulation_result(
        simulation_id=simulation_id,
        model_id=model_id,
        slot_no=1,
        execution_provider="provider-a",
    )
    await factory.simulation_result(
        simulation_id=simulation_id,
        model_id=model_id,
        slot_no=2,
        execution_provider="provider-b",
    )

    await expect_rejected(
        db_session,
        factory.simulation_result(
            simulation_id=simulation_id,
            model_id=model_id,
            slot_no=3,
            execution_provider="provider-a",
        ),
        constraint="uq_sim_results_model_provider_config",
    )


async def _configured_result(
    factory: Factory,
    simulation_id: uuid.UUID,
    model_id: int,
    slot_no: int,
    config: dict[str, Any],
    **values: Any,
) -> RowMapping:
    request = await factory.ai_request(
        usage_origin="SIMULATION",
        simulation_id=simulation_id,
        execution_config=config,
    )
    return await factory.simulation_result(
        simulation_id=simulation_id,
        model_id=model_id,
        request_id=request["request_id"],
        slot_no=slot_no,
        **values,
    )


async def test_same_model_and_provider_accept_different_settings_without_a_hash(
    factory: Factory, db_session: AsyncSession
) -> None:
    simulation_id = (await factory.simulation_run())["simulation_id"]
    model_id = (await factory.model())["model_id"]
    first = await _configured_result(
        factory, simulation_id, model_id, 1, {"temperature": 0.3}
    )
    second = await _configured_result(
        factory, simulation_id, model_id, 2, {"temperature": 0.7}
    )
    assert first["execution_config_hash"] != second["execution_config_hash"]
    assert len(first["execution_config_hash"]) == 64
    await expect_rejected(
        db_session,
        _configured_result(factory, simulation_id, model_id, 3, {"temperature": 0.3}),
        constraint="uq_sim_results_model_provider_config",
    )


@pytest.mark.parametrize(
    ("left", "right", "equal"),
    [
        (
            '{"temperature": 1, "max_tokens": 512}',
            '{"max_tokens": 512.00, "temperature": 1.0}',
            True,
        ),
        (
            '{"reasoning": {"effort": "high", "values": [1, 0.30]}}',
            '{"reasoning": {"values": [1.00, 0.3], "effort": "high"}}',
            True,
        ),
        ('{"value": -0.00}', '{"value": 0}', True),
        ('{"value": "1"}', '{"value": 1}', False),
        ('{"value": true}', '{"value": 1}', False),
        ("{}", '{"temperature": null}', False),
        ('{"value": []}', '{"value": {}}', False),
        ('{"value": [1, 2]}', '{"value": [2, 1]}', False),
        ('{"value": "한글\\n문자"}', '{"value": "한글\\n문자"}', True),
    ],
)
async def test_config_fingerprint_respects_json_value_equality(
    db_session: AsyncSession, left: str, right: str, equal: bool
) -> None:
    same = await db_session.scalar(
        text(
            "SELECT simulation_execution_config_hash(CAST(:left AS jsonb)) = "
            "simulation_execution_config_hash(CAST(:right AS jsonb))"
        ),
        {"left": left, "right": right},
    )
    assert same is equal


async def test_supplied_hash_cannot_bypass_duplicate_detection(
    factory: Factory, db_session: AsyncSession
) -> None:
    simulation_id = (await factory.simulation_run())["simulation_id"]
    model_id = (await factory.model())["model_id"]
    await _configured_result(factory, simulation_id, model_id, 1, {"max_tokens": 512})
    await expect_rejected(
        db_session,
        _configured_result(
            factory,
            simulation_id,
            model_id,
            2,
            {"max_tokens": 512.0},
            execution_config_hash="f" * 64,
        ),
        constraint="uq_sim_results_model_provider_config",
    )


async def test_linked_request_settings_cannot_change_the_result_fingerprint(
    factory: Factory, db_session: AsyncSession
) -> None:
    simulation_id = (await factory.simulation_run())["simulation_id"]
    model_id = (await factory.model())["model_id"]
    result = await _configured_result(
        factory, simulation_id, model_id, 1, {"max_tokens": 512}
    )
    await expect_rejected(
        db_session,
        db_session.execute(
            text(
                "UPDATE ai_requests SET execution_config = '{\"max_tokens\": 1024}' "
                "WHERE request_id = :id"
            ),
            {"id": result["request_id"]},
        ),
        constraint="fk_simulation_results_request_config",
    )
    await expect_rejected(
        db_session,
        factory.ai_request(execution_config_hash="f" * 64),
        sqlstate=GENERATED_ALWAYS_SQLSTATE,
    )


async def test_config_hash_cannot_be_overwritten_on_a_result(
    factory: Factory, db_session: AsyncSession
) -> None:
    result = await factory.simulation_result()
    value = await db_session.scalar(
        text(
            "UPDATE simulation_results SET execution_config_hash = :fake "
            "WHERE request_id = :id RETURNING execution_config_hash"
        ),
        {"fake": "f" * 64, "id": result["request_id"]},
    )
    assert value == result["execution_config_hash"]


async def test_non_final_attempt_does_not_block_the_same_settings(
    factory: Factory,
) -> None:
    simulation_id = (await factory.simulation_run())["simulation_id"]
    model_id = (await factory.model())["model_id"]
    await _configured_result(
        factory, simulation_id, model_id, 1, {}, is_final_attempt=False
    )
    await _configured_result(factory, simulation_id, model_id, 1, {})


@pytest.mark.parametrize("table", ["simulation_runs", "ai_requests"])
@pytest.mark.parametrize("config", ["[]", "null", '"text"', "1", "true"])
async def test_execution_config_requires_a_json_object(
    factory: Factory, db_session: AsyncSession, table: str, config: str
) -> None:
    make = factory.simulation_run if table == "simulation_runs" else factory.ai_request
    row = await make()
    key = "simulation_id" if table == "simulation_runs" else "request_id"
    await expect_rejected(
        db_session,
        db_session.execute(
            text(
                f"UPDATE {table} SET execution_config = CAST(:config AS jsonb) "
                f"WHERE {key} = :id"
            ),
            {"config": config, "id": row[key]},
        ),
        constraint=f"ck_{table}_execution_config_object",
    )


async def test_favorites_are_unique_per_user_model_and_provider(
    factory: Factory, db_session: AsyncSession
) -> None:
    user = await factory.user()
    model = await factory.model()
    values = {
        "user_id": user["user_id"],
        "model_id": model["model_id"],
        "execution_provider": "provider-a",
    }
    favorite = await factory.insert("user_model_favorites", values)
    assert favorite["created_at"].tzinfo is not None
    await expect_rejected(
        db_session,
        factory.insert("user_model_favorites", values),
        constraint="user_model_favorites_pkey",
    )
    await factory.insert(
        "user_model_favorites", {**values, "execution_provider": "provider-b"}
    )
    await factory.insert(
        "user_model_favorites", {**values, "user_id": (await factory.user())["user_id"]}
    )
    await factory.insert(
        "user_model_favorites",
        {**values, "model_id": (await factory.model())["model_id"]},
    )
    await db_session.execute(
        text(
            "DELETE FROM user_model_favorites WHERE user_id = :user_id "
            "AND model_id = :model_id AND execution_provider = :execution_provider"
        ),
        values,
    )
    await factory.insert("user_model_favorites", values)


@pytest.mark.parametrize("provider", ["", " ", " provider-a", "provider-a "])
async def test_favorites_reject_blank_or_untrimmed_provider(
    factory: Factory, db_session: AsyncSession, provider: str
) -> None:
    values = {
        "user_id": (await factory.user())["user_id"],
        "model_id": (await factory.model())["model_id"],
        "execution_provider": provider,
    }
    await expect_rejected(
        db_session,
        factory.insert("user_model_favorites", values),
        constraint="ck_user_model_favorites_provider",
    )


@pytest.mark.parametrize("parent,key", [("users", "user_id"), ("models", "model_id")])
async def test_favorites_require_existing_parents_and_restrict_parent_deletion(
    factory: Factory, db_session: AsyncSession, parent: str, key: str
) -> None:
    values = {
        "user_id": (await factory.user())["user_id"],
        "model_id": (await factory.model())["model_id"],
        "execution_provider": "provider-a",
    }
    constraint = f"user_model_favorites_{key}_fkey"
    await expect_rejected(
        db_session,
        factory.insert("user_model_favorites", {**values, key: -1}),
        constraint=constraint,
    )
    await factory.insert("user_model_favorites", values)
    await expect_rejected(
        db_session,
        db_session.execute(
            text(f"DELETE FROM {parent} WHERE {key} = :id"), {"id": values[key]}
        ),
        constraint=constraint,
    )


async def test_result_request_belongs_to_same_simulation(
    factory: Factory, db_session: AsyncSession
) -> None:
    """fk_simulation_results_request: 다른 실행의 호출을 결과로 연결할 수 없다."""
    other_request = await factory.ai_request(usage_origin="SIMULATION")
    simulation_id = (await factory.simulation_run())["simulation_id"]

    await expect_rejected(
        db_session,
        factory.simulation_result(
            simulation_id=simulation_id, request_id=other_request["request_id"]
        ),
        constraint="fk_simulation_results_request",
    )


async def test_output_asset_order_is_unique_per_request(
    factory: Factory, db_session: AsyncSession
) -> None:
    """uq_output_assets_request_order: 한 호출이 만든 이미지의 순서는 겹치지 않는다."""
    request_id = (await factory.ai_request())["request_id"]
    await factory.output_asset(request_id=request_id, sort_order=0)
    await factory.output_asset(request_id=request_id, sort_order=1)
    await factory.output_asset(sort_order=0)

    await expect_rejected(
        db_session,
        factory.output_asset(request_id=request_id, sort_order=1),
        constraint="uq_output_assets_request_order",
    )


async def test_output_asset_requires_existing_request_and_keeps_it(
    factory: Factory, db_session: AsyncSession
) -> None:
    """결과 이미지는 실제 호출에만 붙고, 이미지가 있는 호출은 지울 수 없다."""
    constraint = "output_assets_request_id_fkey"
    await expect_rejected(
        db_session, factory.output_asset(request_id=uuid.uuid4()), constraint=constraint
    )
    request_id = (await factory.ai_request())["request_id"]
    await factory.output_asset(request_id=request_id)

    await expect_rejected(
        db_session,
        db_session.execute(
            text("DELETE FROM ai_requests WHERE request_id = :id"), {"id": request_id}
        ),
        constraint=constraint,
    )


async def test_task_reference_is_unique_per_service(
    factory: Factory, db_session: AsyncSession
) -> None:
    """uq_tasks_service_ref: 같은 서비스의 같은 작업 번호는 한 번만. 작업 번호가 없으면(NULL) 제한 없음."""
    service_id = (await factory.service())["service_id"]
    await factory.task(service_id=service_id, external_task_ref="JOB-1")
    await factory.task(service_id=service_id, external_task_ref=None)
    await factory.task(service_id=service_id, external_task_ref=None)

    await expect_rejected(
        db_session,
        factory.task(service_id=service_id, external_task_ref="JOB-1"),
        constraint="uq_tasks_service_ref",
    )


async def test_subscription_is_unique_per_month(
    factory: Factory, db_session: AsyncSession
) -> None:
    """uq_subscription_costs_ref_month: 같은 구독은 한 달에 한 번만 입력한다."""
    await factory.subscription_cost(
        subscription_reference="SUB-X", applied_month=MONTH0
    )
    await factory.subscription_cost(
        subscription_reference="SUB-X", applied_month=date(2026, 11, 1)
    )

    await expect_rejected(
        db_session,
        factory.subscription_cost(subscription_reference="SUB-X", applied_month=MONTH0),
        constraint="uq_subscription_costs_ref_month",
    )


async def test_budget_periods_do_not_overlap(
    factory: Factory, db_session: AsyncSession
) -> None:
    """ex_budgets_no_overlap: 같은 대상의 예산 적용 기간은 겹칠 수 없다(종료 월 포함, 종료 NULL = 무기한)."""
    project_id = (await factory.project())["project_id"]
    await factory.budget(
        project_id=project_id, effective_from_month=MONTH0, effective_to_month=MONTH0
    )
    await factory.budget(project_id=project_id, effective_from_month=date(2026, 11, 1))
    await factory.budget(effective_from_month=MONTH0)

    await expect_rejected(
        db_session,
        factory.budget(
            project_id=project_id,
            effective_from_month=MONTH0,
            effective_to_month=MONTH0,
        ),
        constraint="ex_budgets_no_overlap",
    )
    await expect_rejected(
        db_session,
        factory.budget(project_id=project_id, effective_from_month=date(2027, 1, 1)),
        constraint="ex_budgets_no_overlap",
    )


# ---------------------------------------------------------------------------
# 생성 컬럼, 트리거, 삭제 금지
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "owner_type"),
    [
        ("CUSTOMER_SERVICE", "CUSTOMER"),
        ("INTERNAL_DEVELOPMENT", "INTERNAL"),
        ("SIMULATION", "POC"),
        ("SYSTEM_TEST", "POC"),
    ],
)
async def test_owner_type_is_derived_from_origin(
    factory: Factory, origin: str, owner_type: str
) -> None:
    """ai_requests.owner_type은 usage_origin에서 자동으로 계산되어 저장된다."""
    request = await factory.ai_request(usage_origin=origin)

    assert request["owner_type"] == owner_type


async def test_owner_type_cannot_be_written(
    factory: Factory, db_session: AsyncSession
) -> None:
    """owner_type은 직접 넣을 수 없다(설계: 직접 입력 불가)."""
    await expect_rejected(
        db_session,
        factory.ai_request(usage_origin="CUSTOMER_SERVICE", owner_type="INTERNAL"),
        sqlstate=GENERATED_ALWAYS_SQLSTATE,
    )


async def test_owner_type_is_stored_not_virtual(db_session: AsyncSession) -> None:
    """PostgreSQL 18은 STORED를 빼면 VIRTUAL로 만든다. 설계대로 저장(STORED)되는지 확인한다."""
    generated = await db_session.scalar(
        text(
            "SELECT attgenerated FROM pg_attribute "
            "WHERE attrelid = 'ai_requests'::regclass AND attname = 'owner_type'"
        )
    )

    assert generated == "s"


@pytest.mark.parametrize(
    "secret_ref",
    [
        "",
        "COMMAND_CODE_KEY_",
        "command_code_key_a",
        "OPENROUTER_API_KEY",
        "COMMAND_CODE_KEY_0000-0000-0000",
        "0000-0000-0000",
    ],
)
async def test_command_code_key_rejects_anything_but_a_reference_name(
    factory: Factory, db_session: AsyncSession, secret_ref: str
) -> None:
    """Key 원문을 실수로 넣어도 저장되지 않게 정해진 형식의 이름만 받는다."""
    await expect_rejected(
        db_session,
        factory.command_code_key(secret_ref=secret_ref),
        constraint="command_code_keys_secret_ref_check",
    )


async def test_command_code_key_accepts_a_reference_name(factory: Factory) -> None:
    key = await factory.command_code_key(secret_ref="COMMAND_CODE_KEY_MEMBER_01")

    assert key["secret_ref"] == "COMMAND_CODE_KEY_MEMBER_01"
    assert key["is_active"] is True


async def test_command_code_key_reference_is_unique(
    factory: Factory, db_session: AsyncSession
) -> None:
    await factory.command_code_key(secret_ref="COMMAND_CODE_KEY_A")

    await expect_rejected(
        db_session,
        factory.command_code_key(secret_ref="COMMAND_CODE_KEY_A"),
        constraint="command_code_keys_secret_ref_key",
    )


async def test_one_active_command_code_key_per_member(
    factory: Factory, db_session: AsyncSession
) -> None:
    """같은 이름은 사용 중인 Key를 하나만 가지고, 비활성 행은 이력으로 남아도 막지 않는다."""
    await factory.command_code_key(member_name="구성원 A", is_active=False)
    await factory.command_code_key(member_name="구성원 A")

    await expect_rejected(
        db_session,
        factory.command_code_key(member_name="구성원 A"),
        constraint="uq_command_code_keys_active_member",
    )


@pytest.mark.parametrize("member_name", ["", " ", " 구성원", "구성원 "])
async def test_command_code_key_rejects_blank_or_untrimmed_member_name(
    factory: Factory, db_session: AsyncSession, member_name: str
) -> None:
    await expect_rejected(
        db_session,
        factory.command_code_key(member_name=member_name),
        constraint="command_code_keys_member_name_check",
    )


# (테이블, 기본키 컬럼, Factory 메서드): updated_at이 있는 13개 테이블
UPDATED_AT_TABLES = [
    ("customers", "customer_id", "customer"),
    ("projects", "project_id", "project"),
    ("users", "user_id", "user"),
    ("services", "service_id", "service"),
    ("api_keys", "key_id", "api_key"),
    ("command_code_keys", "command_code_key_id", "command_code_key"),
    ("models", "model_id", "model"),
    ("ai_requests", "request_id", "ai_request"),
    ("test_scenarios", "scenario_id", "scenario"),
    ("simulation_runs", "simulation_id", "simulation_run"),
    ("budgets", "budget_id", "budget"),
    ("subscription_costs", "subscription_id", "subscription_cost"),
    ("usage_reconciliations", "reconciliation_id", "usage_reconciliation"),
]


@pytest.mark.parametrize(
    ("table", "pk", "method"),
    UPDATED_AT_TABLES,
    ids=[row[0] for row in UPDATED_AT_TABLES],
)
async def test_updated_at_is_refreshed_on_update(
    factory: Factory, db_session: AsyncSession, table: str, pk: str, method: str
) -> None:
    """행을 수정하면 트리거가 updated_at을 현재 시각으로 바꾼다(옛 시각을 넣어도 덮어씀)."""
    row = await getattr(factory, method)()
    stale = datetime(2000, 1, 1, tzinfo=UTC)

    result = await db_session.execute(
        text(
            f"UPDATE {table} SET updated_at = :stale WHERE {pk} = :id RETURNING updated_at, now()"
        ),
        {"stale": stale, "id": row[pk]},
    )
    updated_at, now = result.one()

    assert updated_at == now


async def test_every_foreign_key_restricts_delete(db_session: AsyncSession) -> None:
    """모든 외래키는 ON DELETE RESTRICT다. 참조되는 이력 행은 지울 수 없다(CLAUDE.md CRITICAL)."""
    result = await db_session.execute(
        text(
            "SELECT conrelid::regclass::text, conname, confdeltype FROM pg_constraint "
            "WHERE contype = 'f' AND connamespace = 'public'::regnamespace"
        )
    )
    foreign_keys = result.all()

    assert foreign_keys
    assert [
        (table, name) for table, name, action in foreign_keys if action != "r"
    ] == []


@pytest.mark.parametrize(
    ("parent_method", "parent_table", "pk", "child_method", "child_fk", "constraint"),
    [
        (
            "customer",
            "customers",
            "customer_id",
            "api_key",
            "customer_id",
            "api_keys_customer_id_fkey",
        ),
        (
            "service",
            "services",
            "service_id",
            "api_key",
            "service_id",
            "api_keys_service_id_fkey",
        ),
        (
            "user",
            "users",
            "user_id",
            "user_session",
            "user_id",
            "user_sessions_user_id_fkey",
        ),
        (
            "model",
            "models",
            "model_id",
            "model_price",
            "model_id",
            "model_prices_model_id_fkey",
        ),
        (
            "ai_request",
            "ai_requests",
            "request_id",
            "ai_request_payload",
            "request_id",
            "ai_request_payloads_request_id_fkey",
        ),
    ],
)
async def test_referenced_rows_cannot_be_deleted(
    factory: Factory,
    db_session: AsyncSession,
    parent_method: str,
    parent_table: str,
    pk: str,
    child_method: str,
    child_fk: str,
    constraint: str,
) -> None:
    """대표 테이블에서 참조되는 행을 지우면 거절된다."""
    parent = await getattr(factory, parent_method)()
    child_values: dict[str, Any] = {child_fk: parent[pk]}
    if child_method == "api_key":
        child_values.update(owner_type="CUSTOMER", project_id=None)
    await getattr(factory, child_method)(**child_values)

    await expect_rejected(
        db_session,
        db_session.execute(
            text(f"DELETE FROM {parent_table} WHERE {pk} = :id"), {"id": parent[pk]}
        ),
        constraint=constraint,
    )

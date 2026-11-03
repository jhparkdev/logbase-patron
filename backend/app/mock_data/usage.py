"""고객 서비스 사용량: 작업(tasks)과 그 안의 호출(ai_requests).

AI PDP 작업은 이미지 속성 분석 1회이거나, 문구 작성 → 평가 → (불합격이면) 재작성이다.
FlipPage 작업은 카탈로그 요약 1회이고 주로 새벽 배치로 돈다. 일시적 오류는 서비스가 한 번 다시 시도한다.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from random import Random

from app.mock_data import routes
from app.mock_data.calls import CallSpec, Shape, build_call
from app.mock_data.demand import DAYS_PER_MONTH, DEMANDS, Demand, spike_factor
from app.mock_data.ids import rng_for, uuid7_at
from app.mock_data.keys import production_key, project_key
from app.mock_data.model_book import ModelBook
from app.mock_data.organizations import AI_PDP, CUSTOMERS, FLIPPAGE, service_id
from app.mock_data.outcomes import sample_outcome
from app.mock_data.period import KST, PERIOD_END
from app.mock_data.rows import Row
from app.mock_data.traffic import (
    HourProfile,
    day_factor,
    period_days,
    poisson,
    sample_time,
)
from app.models import CallPurpose, DataSource, RequestStatus, UsageOrigin

FAILURE_RATE = 0.03
RETRY_FAILURE_RATE = 0.1
REWRITE_SHARE = 0.15  # 평가에서 떨어져 다시 쓰는 문구 비율
IMAGE_TASK_SHARE = 0.3
CALL_GAP_MS = (40, 400)
RETRY_BACKOFF_MS = (1000, 6000)
TASK_PREFIX = {AI_PDP: "PDP", FLIPPAGE: "FLIP"}
# 개발 Key가 운영 배포에 잘못 들어가 고객을 알 수 없게 된 날. 호출은 미분류로 남긴다.
MISCONFIGURED_DAYS = (date(2026, 10, 16), date(2026, 10, 17))
MISCONFIGURED_CALLS_PER_DAY = 6


@dataclass(frozen=True)
class CustomerUsage:
    tasks: list[Row]
    requests: list[Row]


@dataclass
class _Context:
    book: ModelBook
    rng: Random
    requests: list[Row]


def _call(ctx: _Context, spec: CallSpec, at: datetime) -> list[Row]:
    """한 단계를 실행한다. 일시적 오류면 한 번 다시 시도한다. 마지막 시도가 끝에 온다."""
    outcome = sample_outcome(FAILURE_RATE, ctx.rng)
    first = build_call(spec, at, outcome, ctx.book, ctx.rng, PERIOD_END)
    if not outcome.retryable:
        return [first]
    retry_at = first["completed_at"] + timedelta(
        milliseconds=ctx.rng.randint(*RETRY_BACKOFF_MS)
    )
    retry = replace(spec, attempt_no=2, parent_request_id=first["request_id"])
    outcome = sample_outcome(RETRY_FAILURE_RATE, ctx.rng)
    return [first, build_call(retry, retry_at, outcome, ctx.book, ctx.rng, PERIOD_END)]


def _next_start(rows: list[Row], rng: Random) -> datetime:
    return rows[-1]["completed_at"] + timedelta(milliseconds=rng.randint(*CALL_GAP_MS))


def _task_steps(
    demand: Demand, rng: Random
) -> tuple[str, list[tuple[routes.Route, Shape, CallPurpose]]]:
    if demand.service_code != AI_PDP:
        return "CATALOG_SUMMARY", [
            (demand.writer, Shape.CATALOG_SUMMARY, CallPurpose.GENERATION)
        ]
    if rng.random() < IMAGE_TASK_SHARE:
        return "IMAGE_ANALYSIS", [
            (routes.IMAGE_ANALYZER, Shape.IMAGE_ANALYSIS, CallPurpose.GENERATION)
        ]
    steps = [
        (demand.writer, Shape.DESCRIPTION, CallPurpose.GENERATION),
        (routes.PDP_EVALUATOR, Shape.EVALUATION, CallPurpose.EVALUATION),
    ]
    if demand.rewriter is not None and rng.random() < REWRITE_SHARE:
        steps.append((demand.rewriter, Shape.DESCRIPTION, CallPurpose.REGENERATION))
    return "PRODUCT_DESCRIPTION", steps


def _run_task(
    ctx: _Context, demand: Demand, started_at: datetime
) -> tuple[Row, list[Row]] | None:
    task_id = uuid7_at(started_at, ctx.rng)
    task_type, steps = _task_steps(demand, ctx.rng)
    key = production_key(demand.customer_id, demand.service_code)
    rows: list[Row] = []
    at = started_at
    for route, shape, purpose in steps:
        spec = CallSpec(
            usage_origin=UsageOrigin.CUSTOMER_SERVICE,
            key_id=key.key_id,
            service_id=service_id(demand.service_code),
            model_id=routes.pick_model(route, at, ctx.rng),
            shape=shape,
            call_purpose=purpose,
            customer_id=demand.customer_id,
            task_id=task_id,
        )
        rows += _call(ctx, spec, at)
        if rows[-1]["status"] != RequestStatus.SUCCESS:
            break  # 마지막 시도까지 실패하면 다음 단계로 가지 않는다
        at = _next_start(rows, ctx.rng)
    if rows[-1]["completed_at"] > PERIOD_END:
        return None
    task = {
        "task_id": task_id,
        "external_task_ref": None,
        "usage_origin": UsageOrigin.CUSTOMER_SERVICE,
        "customer_id": demand.customer_id,
        "project_id": None,
        "service_id": service_id(demand.service_code),
        "task_type": task_type,
        "started_at": started_at,
        "completed_at": rows[-1]["completed_at"],
        "data_source": DataSource.MOCK,
    }
    return task, rows


def _daily_mean(demand: Demand, usage_from: datetime, day: date) -> float:
    months = (day - usage_from.astimezone(KST).date()).days / DAYS_PER_MONTH
    growth = demand.monthly_growth**months
    return (
        demand.tasks_per_weekday * growth * day_factor(day) * spike_factor(demand, day)
    )


def _misconfigured_calls(ctx: _Context) -> list[Row]:
    key = project_key("PRJ-PDP-DEV", AI_PDP)
    rows: list[Row] = []
    for day in MISCONFIGURED_DAYS:
        for _ in range(MISCONFIGURED_CALLS_PER_DAY):
            at = sample_time(day, HourProfile.BUSINESS, ctx.rng)
            spec = CallSpec(
                usage_origin=UsageOrigin.CUSTOMER_SERVICE,
                key_id=key.key_id,
                service_id=service_id(AI_PDP),
                model_id=routes.pick_model(routes.PDP_WRITER, at, ctx.rng),
                shape=Shape.DESCRIPTION,
                call_purpose=CallPurpose.GENERATION,
            )
            rows += _call(ctx, spec, at)
    return rows


def generate_customer_usage(book: ModelBook) -> CustomerUsage:
    ctx = _Context(book, rng_for("customer-usage"), [])
    customers = {c.customer_id: c for c in CUSTOMERS}
    tasks: list[Row] = []
    for demand in DEMANDS:
        customer = customers[demand.customer_id]
        profile = (
            HourProfile.BUSINESS
            if demand.service_code == AI_PDP
            else HourProfile.NIGHTLY_BATCH
        )
        for day in period_days():
            count = poisson(_daily_mean(demand, customer.usage_from, day), ctx.rng)
            starts = sorted(sample_time(day, profile, ctx.rng) for _ in range(count))
            for started_at in starts:
                if started_at < customer.usage_from:
                    continue
                if (
                    customer.usage_until is not None
                    and started_at >= customer.usage_until
                ):
                    continue
                result = _run_task(ctx, demand, started_at)
                if result is not None:
                    tasks.append(result[0])
                    ctx.requests += result[1]
    ctx.requests += _misconfigured_calls(ctx)
    _number_tasks(tasks)
    ctx.requests.sort(key=lambda row: row["requested_at"])
    return CustomerUsage(tasks, ctx.requests)


def _number_tasks(tasks: list[Row]) -> None:
    """서비스가 붙이는 작업 번호(PDP-20261001-0001). 서비스·날짜마다 1부터 센다."""
    tasks.sort(key=lambda task: task["started_at"])
    counters: dict[tuple[object, date], int] = {}
    prefixes = {service_id(code): prefix for code, prefix in TASK_PREFIX.items()}
    for task in tasks:
        day = task["started_at"].astimezone(KST).date()
        counter_key = (task["service_id"], day)
        counters[counter_key] = counters.get(counter_key, 0) + 1
        prefix = prefixes[task["service_id"]]
        task["external_task_ref"] = f"{prefix}-{day:%Y%m%d}-{counters[counter_key]:04d}"

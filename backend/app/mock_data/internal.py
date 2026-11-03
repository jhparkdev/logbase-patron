"""내부 개발 호출: 프로젝트 Key로 하는 일상 개발 호출과 새 모델 실험.

새 모델이 활성화되면 그 주에 AI PDP 개발 프로젝트에서 실험 호출이 몰린다.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from random import Random

from app.mock_data import routes
from app.mock_data.calls import CallSpec, Shape, build_call
from app.mock_data.ids import rng_for
from app.mock_data.keys import MockKey, project_key
from app.mock_data.model_book import ModelBook
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import AI_PDP, FLIPPAGE, INTERNAL_TOOL, service_id
from app.mock_data.outcomes import sample_outcome
from app.mock_data.period import PERIOD_END, PERIOD_START
from app.mock_data.rows import Row
from app.mock_data.traffic import (
    HOLIDAYS,
    HourProfile,
    period_days,
    poisson,
    sample_time,
)
from app.models import CallPurpose, UsageOrigin

FAILURE_RATE = 0.04
SATURDAY = 5
EXPERIMENT_CALLS = (18, 30)
EXPERIMENT_WINDOW_DAYS = 7


@dataclass(frozen=True)
class _Workload:
    project_code: str
    service_code: str
    route: routes.Route
    shape: Shape
    calls_per_workday: float


WORKLOADS = (
    _Workload("PRJ-PDP-DEV", AI_PDP, routes.INTERNAL_WRITER, Shape.DESCRIPTION, 2.0),
    _Workload(
        "PRJ-PDP-DEV",
        INTERNAL_TOOL,
        routes.INTERNAL_TOOL_ASSISTANT,
        Shape.EXPERIMENT,
        1.2,
    ),
    _Workload(
        "PRJ-PDP-DEV",
        INTERNAL_TOOL,
        routes.INTERNAL_LONG_DOCS,
        Shape.CATALOG_SUMMARY,
        0.5,
    ),
    _Workload(
        "PRJ-CUST-RENEWAL",
        FLIPPAGE,
        routes.CATALOG_SUMMARIZER,
        Shape.CATALOG_SUMMARY,
        0.8,
    ),
)


def _development_spec(
    key: MockKey, model_id: int, shape: Shape, purpose: CallPurpose
) -> CallSpec:
    return CallSpec(
        usage_origin=UsageOrigin.INTERNAL_DEVELOPMENT,
        key_id=key.key_id,
        service_id=service_id(key.service_code or AI_PDP),
        model_id=model_id,
        shape=shape,
        call_purpose=purpose,
        project_id=key.project_id,
    )


def _is_workday(day: date) -> bool:
    return day.weekday() < SATURDAY and day not in HOLIDAYS


def _experiment_times(activated_at: datetime, rng: Random) -> list[datetime]:
    first_day = activated_at.date()
    days = [
        first_day + timedelta(days=offset) for offset in range(EXPERIMENT_WINDOW_DAYS)
    ]
    times = [
        sample_time(rng.choice(days), HourProfile.BUSINESS, rng)
        for _ in range(rng.randint(*EXPERIMENT_CALLS))
    ]
    return sorted(at for at in times if activated_at <= at < PERIOD_END)


def generate_development_calls(book: ModelBook) -> list[Row]:
    rng = rng_for("internal-development")
    rows: list[Row] = []
    for workload in WORKLOADS:
        key = project_key(workload.project_code, workload.service_code)
        for day in filter(_is_workday, period_days()):
            for _ in range(poisson(workload.calls_per_workday, rng)):
                at = sample_time(day, HourProfile.BUSINESS, rng)
                model = routes.pick_model(workload.route, at, rng)
                spec = _development_spec(
                    key, model, workload.shape, CallPurpose.GENERATION
                )
                rows.append(
                    build_call(
                        spec,
                        at,
                        sample_outcome(FAILURE_RATE, rng),
                        book,
                        rng,
                        PERIOD_END,
                    )
                )
    experiment_key = project_key("PRJ-PDP-DEV", AI_PDP)
    for plan in MODEL_PLANS:
        if plan.activated_at is None or plan.activated_at < PERIOD_START:
            continue
        for at in _experiment_times(plan.activated_at, rng):
            if plan.deactivated_at is not None and at >= plan.deactivated_at:
                continue
            spec = _development_spec(
                experiment_key, plan.model_id, Shape.EXPERIMENT, CallPurpose.EXPERIMENT
            )
            rows.append(
                build_call(
                    spec, at, sample_outcome(FAILURE_RATE, rng), book, rng, PERIOD_END
                )
            )
    rows = [row for row in rows if row["completed_at"] <= PERIOD_END]
    rows.sort(key=lambda row: row["requested_at"])
    return rows

"""시뮬레이션 실행 계획: 언제, 누가, 어떤 시나리오로, 어떤 모델들을 비교했는가.

새 모델이 나온 9월 말 이후에 비교가 몰리고, 갓 등록한 모델이 비교 대상으로 자주 뽑힌다.
기본 실행을 다 만든 뒤, 일부가 실패한 실행 몇 건을 같은 조건으로 재실행한다.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from random import Random

from pydantic import JsonValue

from app.mock_data import routes, sim_content
from app.mock_data.members import USERS
from app.mock_data.model_book import ModelBook
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.period import KST, PERIOD_START, kst
from app.mock_data.rows import Row
from app.mock_data.scenarios import CHANGED_AT, by_code
from app.mock_data.sim_inputs import CUSTOM, Answer, custom_input, scenario_input
from app.mock_data.traffic import HOLIDAYS
from app.models import SimulationStatus, TestType
from app.services.simulation_input import resolve_execution_config

RUN_COUNT = 40
RERUN_COUNT = 3
LAST_RUN_DAY = date(2026, 11, 5)
BUSY_FROM = date(2026, 9, 20)  # 새 모델이 연달아 나온 뒤부터 비교가 잦아진다
BUSY_WEIGHT = 3
WORK_HOURS = (9, 18)
SATURDAY = 5
MODEL_COUNT_WEIGHTS = {2: 3, 3: 5, 4: 2}
NEW_MODEL_WINDOW = timedelta(days=14)
NEW_MODEL_WEIGHT = 4
REASONING_EFFORT_SHARE = 0.2
RERUN_DELAY_DAYS = (1, 3)
SCENARIO_WEIGHTS = {
    "PRODUCT_COPY": 34,
    "TEXT_TO_JSON": 24,
    "DATA_SUMMARY": 18,
    "GENERAL_REASONING": 10,
    CUSTOM: 14,
}
# 이미지를 만드는 모델은 글 비교 실행에 넣지 않는다.
IMAGE_OUTPUT_MODELS = {routes.model_id("google/gemini-nano-banana-2.1")}
KIMI = routes.model_id("moonshotai/kimi-k3.1-pro")


@dataclass(frozen=True)
class RunPlan:
    requested_at: datetime
    test_type: TestType
    scenario_id: int | None
    prompt_text: str
    input_text: str
    json_schema: dict[str, JsonValue] | None
    execution_config: dict[str, JsonValue]
    slots: tuple[tuple[int, str], ...]  # (model_id, 고정한 실행 Provider)
    executed_by: int
    answer: Answer
    cancelled: bool = False
    rerun_of: uuid.UUID | None = None


@dataclass(frozen=True)
class _Forced:
    requested_at: datetime
    scenario_code: str
    models: tuple[int, ...] | None = None
    cancelled: bool = False


FORCED = (
    # 느린 고성능 모델 셋을 비교하다가 응답을 기다리지 않고 취소한 실행
    _Forced(kst(10, 28, 16, 5), "PRODUCT_COPY", (routes.OPUS, routes.SOL, KIMI), True),
    # 데이터 요약 시나리오가 구조화 조건으로 바뀐 뒤의 실행
    _Forced(kst(11, 3, 15, 10), "DATA_SUMMARY"),
    _Forced(kst(11, 4, 14, 20), "DATA_SUMMARY"),
)


def _available_models(at: datetime) -> list[int]:
    return [
        p.model_id
        for p in MODEL_PLANS
        if p.registered_at <= at
        and (p.deactivated_at is None or at < p.deactivated_at)
        and p.model_id not in IMAGE_OUTPUT_MODELS
    ]


def _pick_models(at: datetime, rng: Random) -> list[int]:
    plans = {p.model_id: p for p in MODEL_PLANS}
    pool = _available_models(at)
    count = min(
        len(pool),
        rng.choices(
            list(MODEL_COUNT_WEIGHTS), weights=list(MODEL_COUNT_WEIGHTS.values())
        )[0],
    )
    chosen: list[int] = []
    while len(chosen) < count:
        weights = [
            NEW_MODEL_WEIGHT if at - plans[m].registered_at < NEW_MODEL_WINDOW else 1
            for m in pool
        ]
        model = rng.choices(pool, weights=weights)[0]
        chosen.append(model)
        pool.remove(model)
    return chosen


def _workdays() -> list[date]:
    first = PERIOD_START.astimezone(KST).date()
    days = (first + timedelta(days=n) for n in range((LAST_RUN_DAY - first).days + 1))
    return [d for d in days if d.weekday() < SATURDAY and d not in HOLIDAYS]


def _work_time(day: date, rng: Random) -> datetime:
    return datetime(
        day.year,
        day.month,
        day.day,
        rng.randint(*WORK_HOURS),
        rng.randrange(60),
        tzinfo=KST,
    )


def _member_at(at: datetime, rng: Random, preferred: int | None = None) -> int:
    active = [u.user_id for u in USERS if u.can_act_at(at)]
    return preferred if preferred in active else rng.choice(active)


def _plan(
    at: datetime,
    code: str,
    models: list[int],
    book: ModelBook,
    rng: Random,
    cancelled: bool = False,
) -> RunPlan:
    product = rng.choice(sim_content.PRODUCTS)
    if code == CUSTOM:
        prompt, input_text, answer = custom_input(product, rng)
        config = resolve_execution_config({"temperature": 0.7}, None)
        scenario_id, schema, test_type = None, None, TestType.CUSTOM
    else:
        scenario = by_code(code)
        prompt, input_text, answer = scenario_input(code, product, at, rng)
        requested = (
            {"reasoning_effort": "medium"}
            if rng.random() < REASONING_EFFORT_SHARE
            else {}
        )
        config = resolve_execution_config(requested, scenario.default_execution_config)
        before_change = code == "DATA_SUMMARY" and at < CHANGED_AT
        scenario_id, test_type = scenario.scenario_id, TestType.SCENARIO
        schema = None if before_change else scenario.default_json_schema
    slots = tuple((m, rng.choice(book[m].profile.providers)) for m in models)
    return RunPlan(
        at,
        test_type,
        scenario_id,
        prompt,
        input_text,
        schema,
        config,
        slots,
        _member_at(at, rng),
        answer,
        cancelled,
    )


def _rerun(original: RunPlan, run: Row, rng: Random) -> RunPlan | None:
    day = original.requested_at.date() + timedelta(days=rng.randint(*RERUN_DELAY_DAYS))
    while day.weekday() >= SATURDAY or day in HOLIDAYS:
        day += timedelta(days=1)
    if day > LAST_RUN_DAY:
        return None
    at = _work_time(day, rng)
    if any(m not in _available_models(at) for m, _ in original.slots):
        return None
    executed_by = _member_at(at, rng, preferred=original.executed_by)
    return replace(
        original,
        requested_at=at,
        executed_by=executed_by,
        rerun_of=run["simulation_id"],
    )


def plan_runs(book: ModelBook, rng: Random, built: list[Row]) -> Iterator[RunPlan]:
    """실행 계획을 하나씩 돌려준다. 재실행은 호출한 쪽이 기본 실행을 built에 쌓은 뒤 정한다."""
    days = _workdays()
    weights = [BUSY_WEIGHT if day >= BUSY_FROM else 1 for day in days]
    times = sorted(
        _work_time(day, rng) for day in rng.choices(days, weights=weights, k=RUN_COUNT)
    )
    codes = list(SCENARIO_WEIGHTS)
    planned: list[RunPlan] = []
    for at in times:
        code = rng.choices(codes, weights=list(SCENARIO_WEIGHTS.values()))[0]
        planned.append(_plan(at, code, _pick_models(at, rng), book, rng))
        yield planned[-1]
    for forced in FORCED:
        models = (
            list(forced.models)
            if forced.models
            else _pick_models(forced.requested_at, rng)
        )
        planned.append(
            _plan(
                forced.requested_at,
                forced.scenario_code,
                models,
                book,
                rng,
                forced.cancelled,
            )
        )
        yield planned[-1]
    candidates = sorted(
        (i for i, plan in enumerate(planned) if not plan.cancelled),
        key=lambda i: built[i]["status"] == SimulationStatus.SUCCESS,
    )
    reruns = 0
    for index in candidates:
        if reruns == RERUN_COUNT:
            break
        rerun = _rerun(planned[index], built[index], rng)
        if rerun is not None:
            reruns += 1
            yield rerun

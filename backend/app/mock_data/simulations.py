"""모델 비교 시뮬레이션: 실행(simulation_runs), 칸별 결과, 호출, 요청·응답 원문.

입력 해시, 라우팅 정책, 실행 설정, 전체 상태, JSON 검증은 앱의 함수를 그대로 써서 화면이 계산하는
값과 어긋나지 않게 한다. 자동 재시도는 없고(비교 조건과 비용이 바뀌므로), 다시 하려면 새 ID로 재실행한다.
이미지 입력·생성 실행은 만들지 않는다. 이미지 파일은 DB가 아니라 서버 저장소에 있어 seed로 옮길 수 없다.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from random import Random

from app.mock_data import sim_content
from app.mock_data.calls import CallSpec, Shape, build_call
from app.mock_data.ids import rng_for, uuid7_at
from app.mock_data.keys import poc_key
from app.mock_data.model_book import ModelBook
from app.mock_data.model_plans import MODEL_PLANS, ModelPlan
from app.mock_data.organizations import service_id
from app.mock_data.outcomes import FAILURES, SUCCESS, Outcome
from app.mock_data.period import PERIOD_END
from app.mock_data.rows import Row
from app.mock_data.sim_content import Tier
from app.mock_data.sim_plan import RunPlan, plan_runs
from app.models import CallPurpose, DataSource, ErrorType, RequestStatus, UsageOrigin
from app.services.simulation_input import (
    SIMULATION_TIMEOUT_SECONDS,
    build_prompt_text,
    build_request_routing_policy,
    build_run_routing_policy,
    compute_input_hash,
)
from app.services.simulation_json_check import check_json_output
from app.services.simulation_lookup import SIMULATOR_SERVICE_CODE
from app.services.simulation_status import compute_overall_status

START_DELAY = timedelta(seconds=1)
HEARTBEAT = timedelta(seconds=30)
MS_PER_SECOND = 1000
FAILURE_RATE = 0.08
DISTINCT_ANSWER_TRIES = 5
SYSTEM_PROMPT_TOKENS = 12
TOKENS_PER_CHAR = 0.9  # 한국어 글자 수 → Token 수 어림값
SIMULATION_TIMEOUT = replace(
    FAILURES[ErrorType.TIMEOUT_ERROR],
    latency_ms=(SIMULATION_TIMEOUT_SECONDS * MS_PER_SECOND,) * 2,
)
CANCELLED = Outcome(RequestStatus.CANCELLED, http_status=None, latency_ms=(2000, 5000))
SIMULATION_FAILURES = (
    (FAILURES[ErrorType.PROVIDER_ERROR], 5),
    (SIMULATION_TIMEOUT, 3),
    (FAILURES[ErrorType.RATE_LIMIT], 2),
)


@dataclass(frozen=True)
class Simulations:
    runs: list[Row]
    results: list[Row]
    requests: list[Row]
    payloads: list[Row]


def _tokens(text: str) -> int:
    return max(1, round(len(text) * TOKENS_PER_CHAR))


def _status_at(plan: ModelPlan, at: datetime) -> str:
    return (
        "ACTIVE"
        if plan.activated_at is not None and plan.activated_at <= at
        else "TESTING"
    )


def _outcome(plan: RunPlan, rng: Random) -> Outcome:
    if plan.cancelled:
        return CANCELLED
    if rng.random() >= FAILURE_RATE:
        return SUCCESS
    outcomes, weights = zip(*SIMULATION_FAILURES, strict=True)
    return rng.choices(outcomes, weights=weights)[0]


def _distinct_answer(plan: RunPlan, tier: Tier, seen: set[str], rng: Random) -> str:
    """같은 실행에서 다른 모델과 글자까지 같은 글 답을 피한다. JSON 답은 정답이 같을 수 있어 그대로 둔다."""
    answer = plan.answer(tier, rng)
    for _ in range(DISTINCT_ANSWER_TRIES):
        if plan.json_schema is not None or answer not in seen:
            break
        answer = plan.answer(tier, rng)
    return answer


def _heartbeat(started_at: datetime, completed_at: datetime) -> datetime:
    beats = (completed_at - started_at) // HEARTBEAT
    return started_at + beats * HEARTBEAT


def _build_run(plan: RunPlan, book: ModelBook, rng: Random, out: Simulations) -> None:
    simulation_id = uuid7_at(plan.requested_at, rng)
    started_at = plan.requested_at + START_DELAY
    run_policy = build_run_routing_policy(
        allow_fallbacks=False, has_json_schema=plan.json_schema is not None
    )
    input_hash = compute_input_hash(plan.prompt_text, plan.input_text)
    message = build_prompt_text(plan.prompt_text, plan.input_text)
    plans = {p.model_id: p for p in MODEL_PLANS}
    statuses, completed, answers = [], [], set()
    for slot_no, (model_id, provider) in enumerate(plan.slots, start=1):
        entry = book[model_id]
        outcome = _outcome(plan, rng)
        tier = sim_content.MODEL_TIERS[entry.openrouter_id]
        answer = (
            _distinct_answer(plan, tier, answers, rng)
            if outcome.status == RequestStatus.SUCCESS
            else None
        )
        spec = CallSpec(
            usage_origin=UsageOrigin.SIMULATION,
            key_id=poc_key().key_id,
            service_id=service_id(SIMULATOR_SERVICE_CODE),
            model_id=model_id,
            shape=Shape.EXPERIMENT,
            call_purpose=CallPurpose.EXPERIMENT,
            project_id=poc_key().project_id,
            executed_by=plan.executed_by,
            simulation_id=simulation_id,
            routing_policy=build_request_routing_policy(run_policy, provider),
            requested_provider=provider,
            execution_config=plan.execution_config,
            tokens=(SYSTEM_PROMPT_TOKENS + _tokens(message), _tokens(answer or "")),
            input_hash=input_hash,
        )
        request = build_call(spec, started_at, outcome, book, rng, PERIOD_END)
        if answer is not None:
            answers.add(answer)
        check = check_json_output(answer, plan.json_schema)
        out.requests.append(request)
        out.payloads.append(
            {
                "request_id": request["request_id"],
                "request_messages": [{"role": "user", "content": message}],
                "response_text": answer,
                "response_raw": None,
            }
        )
        out.results.append(
            {
                "simulation_id": simulation_id,
                "request_id": request["request_id"],
                "slot_no": slot_no,
                "model_id": model_id,
                "execution_provider": provider,
                "model_status_at_run": _status_at(plans[model_id], started_at),
                "model_display_name_at_run": entry.display_name,
                "is_final_attempt": True,
                "json_parse_status": check.json_parse_status,
                "schema_validation_status": check.schema_validation_status,
                "missing_required_fields": check.missing_required_fields,
                "validation_errors": check.validation_errors,
                "comparability_note": None,
            }
        )
        statuses.append(request["status"])
        completed.append(request["completed_at"])
    out.runs.append(
        {
            "simulation_id": simulation_id,
            "rerun_of_simulation_id": plan.rerun_of,
            "test_type": plan.test_type,
            "scenario_id": plan.scenario_id,
            "prompt_text": plan.prompt_text,
            "input_text": plan.input_text,
            "json_schema": plan.json_schema,
            "execution_config": plan.execution_config,
            "routing_policy": run_policy,
            "input_hash": input_hash,
            "model_count": len(plan.slots),
            "status": compute_overall_status(statuses),
            "project_id": poc_key().project_id,
            "key_id": poc_key().key_id,
            "executed_by": plan.executed_by,
            "requested_at": plan.requested_at,
            "started_at": started_at,
            "completed_at": max(completed),
            "heartbeat_at": _heartbeat(started_at, max(completed)),
            "data_source": DataSource.MOCK,
        }
    )


def generate_simulations(book: ModelBook) -> Simulations:
    rng = rng_for("simulations")
    out = Simulations([], [], [], [])
    for plan in plan_runs(book, rng, out.runs):
        _build_run(plan, book, rng, out)
    out.runs.sort(key=lambda row: row["requested_at"])
    return out

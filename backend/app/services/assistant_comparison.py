"""한 실행의 저장된 수치만 비교한다. 원문 해석이나 모델의 평가를 사용하지 않는다."""

from decimal import localcontext

from app.models import CostStatus, RequestStatus, SimulationStatus, ValidationStatus
from app.schemas.simulation_result import (
    SimulationDetailResponse,
    SimulationModelResult,
)
from app.schemas.simulation_types import MONEY_MAX_DIGITS
from app.services.assistant_answers import STATUS_LABELS, money

VALIDATION_LABELS = {
    ValidationStatus.PASSED: "통과",
    ValidationStatus.FAILED: "실패",
    ValidationStatus.NOT_APPLICABLE: "미적용",
    ValidationStatus.NOT_EXECUTED: "미실행",
    None: "미확인",
}
COST_LABELS = {CostStatus.CONFIRMED: "확정", CostStatus.ESTIMATED: "추정"}


def _count(value: int | None, unit: str) -> str:
    return "미확인" if value is None else f"{value:,}{unit}"


def _slot(row: SimulationModelResult) -> str:
    cost = (
        "비용 미확인"
        if row.cost_usd is None
        else f"비용 {money(str(row.cost_usd))} ({COST_LABELS[row.cost_status]})"
    )
    latency = (
        "응답시간 미확인"
        if row.latency_ms is None
        else f"응답시간 {row.latency_ms:,}ms"
    )
    name = " ".join(row.model_display_name_at_run.splitlines())
    provider = " ".join(row.execution_provider.splitlines())
    lines = [
        f"{row.slot_no}번 · {name} · 요청 업체 {provider}",
        f"{STATUS_LABELS[row.status]} · {cost} · {latency}",
        f"입력 {_count(row.input_tokens, '토큰')} · 출력 {_count(row.output_tokens, '토큰')}",
        f"JSON {VALIDATION_LABELS[row.json_parse_status]} · Schema {VALIDATION_LABELS[row.schema_validation_status]}",
    ]
    if row.actual_provider and row.actual_provider != row.execution_provider:
        lines.append(f"실제 처리 업체: {' '.join(row.actual_provider.splitlines())}")
    return "\n".join(lines)


def _winners(slots: list[int]) -> str:
    return ", ".join(f"{slot}번" for slot in slots) + (
        " (동률)" if len(slots) > 1 else ""
    )


def _rank(rows: list[SimulationModelResult]) -> list[str]:
    lines = []
    if all(
        row.cost_status == CostStatus.CONFIRMED and row.cost_usd is not None
        for row in rows
    ):
        costs = {row.slot_no: row.cost_usd for row in rows if row.cost_usd is not None}
        low, high = min(costs.values()), max(costs.values())
        lines.append(
            "최저 비용: "
            + _winners([slot for slot, value in costs.items() if value == low])
        )
        if high != low:
            # 저장된 금액의 최대 자릿수에서도 차액이 반올림되지 않도록 한다.
            with localcontext() as context:
                context.prec = MONEY_MAX_DIGITS * 2
                lines.append(f"성공 항목 최고·최저 비용 차이 {money(str(high - low))}")
    else:
        lines.append(
            "성공 항목의 확정 비용이 모두 확인되지 않아 최저 비용은 판단하지 않았어요."
        )
    if all(row.latency_ms is not None for row in rows):
        times = {
            row.slot_no: row.latency_ms for row in rows if row.latency_ms is not None
        }
        low, high = min(times.values()), max(times.values())
        lines.append(
            "가장 짧은 응답시간: "
            + _winners([slot for slot, value in times.items() if value == low])
        )
        if high != low:
            lines.append(f"성공 항목 최장·최단 응답시간 차이 {high - low:,}ms")
    else:
        lines.append(
            "성공 항목의 응답시간이 모두 확인되지 않아 시간 순위는 판단하지 않았어요."
        )
    return lines


def compare_simulation(detail: SimulationDetailResponse) -> str:
    summary = detail.summary
    rows = sorted(detail.results, key=lambda row: row.slot_no)
    if not rows:
        return "비교할 모델별 결과가 없어요. 실행이 끝난 뒤 다시 요청해 주세요."
    parts = [
        f"이번 실행의 정량 비교예요. 요청 시각: {summary.requested_at.isoformat()}",
        *(_slot(row) for row in rows),
    ]
    success = [row for row in rows if row.status == RequestStatus.SUCCESS]
    if summary.status in {SimulationStatus.PENDING, SimulationStatus.RUNNING} or any(
        row.status in {RequestStatus.PENDING, RequestStatus.RUNNING} for row in rows
    ):
        parts.append(
            "진행 중인 실행이라 현재 값만 표시했어요. 순위는 종료 후 확인해 주세요."
        )
    elif len(rows) != summary.model_count:
        parts.append("일부 항목의 결과가 없어 순위를 판단하지 않았어요.")
    elif len(success) < 2:
        parts.append(
            "성공한 항목이 2개 이상이어야 비용·응답시간 순위를 비교할 수 있어요."
        )
    else:
        parts.append(
            f"성공한 {len(success)}개 항목 기준이에요. 실패·취소 항목은 순위에서 제외했어요."
        )
        parts.append("\n".join(_rank(success)))
    if any(
        row.execution_config != rows[0].execution_config
        or row.output_type != rows[0].output_type
        for row in rows[1:]
    ):
        parts.append(
            "항목별 실행 설정이 달라 동일 조건의 성능 비교로 해석할 수 없어요."
        )
    parts.append(
        "이번 실행의 관측값이며 일반적인 성능 순위나 응답 품질·정확도 평가는 아니에요."
    )
    return "\n\n".join(parts)

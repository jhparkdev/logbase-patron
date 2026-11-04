"""조회 서비스가 확정한 금액·시각을 재계산 없이 답변에 표시한다."""

from decimal import Decimal
from typing import Any

from app.services.assistant_models import model_answer

STATUS_LABELS = {
    "PENDING": "대기",
    "RUNNING": "실행 중",
    "SUCCESS": "성공",
    "PARTIAL_SUCCESS": "부분 성공",
    "FAILED": "실패",
    "TIMEOUT": "시간 초과",
    "CANCELLED": "취소",
}


def money(value: str | None) -> str:
    if value is None:
        return "비용 미확인"
    amount = format(Decimal(value), "f")
    return (amount.rstrip("0").rstrip(".") if "." in amount else amount) + " USD"


def unknown_note(data: dict[str, Any]) -> str:
    count = data.get("unknown_cost_count", 0)
    return (
        f"금액 미확인 {count}건은 합계에서 제외했어요. 미확인 금액은 0달러가 아니에요."
        if count
        else ""
    )


def usage_answer(name: str, result: dict[str, Any]) -> str | None:
    data = result.get("data", {})
    conditions = result.get("conditions", {})
    entities = result.get("matched_entities", {})
    target = entities.get("customer") or entities.get("project") or "전체"
    filters = [
        entities[key]
        for key in ("service", "model")
        if entities.get(key) not in {None, "전체"}
    ]
    header = f"{target} · {conditions.get('start_date', '')} ~ {conditions.get('end_date', '')}"
    if filters:
        header += " · " + " · ".join(filters)
    if result.get("section") == "summary":
        if name == "get_internal_usage" and "total_managed_usd" in data:
            lines = [
                f"확정 API 비용: {money(data['api_confirmed_usd'])}",
                f"추정 API 비용: {money(data['api_estimated_usd'])}",
                "모델 필터로 구독료는 제외했어요."
                if data.get("subscription_excluded")
                else f"구독료: {money(data['subscription_usd'])}",
                f"관리 비용(추정 포함): {money(data['total_managed_usd'])}",
            ]
        elif name == "get_customer_usage" and "confirmed_cost_usd" in data:
            lines = [
                f"확정 API 비용: {money(data['confirmed_cost_usd'])}",
                f"추정 API 비용: {money(data['estimated_cost_usd'])}",
            ]
        else:
            return None
        return header + "\n\n" + "\n".join(lines) + "\n\n" + unknown_note(data)
    if result.get("section") == "requests" and "items" in data:
        rows = data["items"]
        label = {"CONFIRMED": "확정", "ESTIMATED": "추정", "UNKNOWN": "미확인"}
        lines = [
            f"- {row['requested_at']} · {money(row.get('cost_usd'))} ({label.get(row.get('cost_status'), '미확인')})"
            for row in rows
        ]
        return (
            header
            + f"\n\n조회 기간의 전체 {data['total']}건 중 {len(rows)}건이에요.\n"
            + ("\n".join(lines) if lines else "조건에 맞는 호출이 없어요.")
        )
    return None


def simulation_line(row: dict[str, Any]) -> str:
    state = STATUS_LABELS.get(row["status"], "상태 확인 필요")
    return f"{row['requested_at']} · {state} · {money(row.get('total_cost_usd'))} ({row['cost_check_status']})"


def intermediate_result(result: dict[str, Any]) -> bool:
    """오류나 이름 목록처럼 답변 본문이 아니라 다음 조회를 위한 결과인지."""
    return "error" in result or result.get("section") == "options"


def verified_answer(name: str, result: dict[str, Any]) -> str | None:
    if name in {"get_customer_usage", "get_internal_usage"}:
        return usage_answer(name, result)
    if name == "find_models" and "items" in result:
        return model_answer(result)
    if name == "get_simulation" and "summary" in result:
        row = result["summary"]
        lines = [f"요청 시각·실행 상태·비용: {simulation_line(row)}", unknown_note(row)]
        for item in result.get("results", []):
            lines.append(
                f"- {item['model_display_name_at_run']} · {STATUS_LABELS.get(item['status'], '상태 확인 필요')} · {money(item.get('cost_usd'))}"
            )
        return "\n\n".join(line for line in lines if line)
    if name == "list_simulations" and "items" in result:
        rows = result["items"]
        return (
            f"시뮬레이션 이력 전체 {result['total']}건 중 {len(rows)}건이에요.\n\n"
            + (
                "\n".join(f"- {simulation_line(row)}" for row in rows)
                if rows
                else "조건에 맞는 실행이 없어요."
            )
        )
    return None

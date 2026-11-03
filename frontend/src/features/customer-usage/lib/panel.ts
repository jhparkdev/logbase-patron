import type { components } from "../../../shared/api/schema";
import { formatUsd, isZeroAmount } from "../../../shared/lib/format";

type Schemas = components["schemas"];

const FULL_PERCENT = 100;

/** 요약 카드의 남은 예산 줄. 예산이 없으면 두지 않고, 넘었으면 음수 대신 초과 금액으로 보여 준다. */
export function remainingBudget(remaining: string | null) {
  if (remaining === null) {
    return undefined;
  }
  return remaining.startsWith("-")
    ? { label: "초과 금액", amount: remaining.slice(1), over: true }
    : { label: "남은 예산", amount: remaining, over: false };
}

/** 서비스가 고객 예산에서 차지하는 비중. 글자는 실제 비중, 막대는 100%에서 멈춘다. */
export function serviceBudgetShare(sharePct: string | null): {
  label: string;
  width?: number;
} {
  if (sharePct === null) {
    return { label: "예산 미설정" };
  }
  const percent = Math.round(Number(sharePct));
  return {
    label: `예산의 ${percent}%`,
    width: Math.min(percent, FULL_PERCENT),
  };
}

/** 막대에 둘 주의 기준선. 서버가 판정에 쓰는 값이라 화면에 숫자를 박지 않는다. 예산이 없으면 두지 않는다 */
export function warningMark(
  budget: Pick<Schemas["BudgetUsage"], "status" | "warning_threshold_pct">,
): number | undefined {
  return budget.status === "UNSET"
    ? undefined
    : Math.round(Number(budget.warning_threshold_pct));
}

const ESTIMATE_NOTE = "추정 포함";

/** 서비스별 합계. 서버가 더한 값만 쓰고, 추정이 섞였으면 ≈와 안내를 붙인다 */
export function serviceTotal(
  service: Pick<
    Schemas["CustomerServiceUsage"],
    "total_cost_usd" | "estimated_cost_usd"
  >,
): { label: string; note: string | undefined } {
  const estimated = !isZeroAmount(service.estimated_cost_usd);
  const amount = formatUsd(service.total_cost_usd, "summary");
  return {
    label: estimated ? `≈ ${amount}` : amount,
    note: estimated ? ESTIMATE_NOTE : undefined,
  };
}

import type { components } from "../../../shared/api/schema";
import { formatUsd, isZeroAmount } from "../../../shared/lib/format";

type Schemas = components["schemas"];

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

/** 월 예산 폼 안내. 주의 기준은 서버 값이라 숫자를 화면에 박지 않는다 */
export function budgetFormHint(
  budget: Pick<Schemas["BudgetUsage"], "warning_threshold_pct">,
): string {
  const threshold = Math.round(Number(budget.warning_threshold_pct));
  return `한 번 정하면 다음 달에도 그대로 적용돼요. 사용률이 ${threshold}% 이상이면 주의, 100% 이상이면 초과로 표시해요.`;
}

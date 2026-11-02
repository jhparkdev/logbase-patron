import type { components } from "../../../shared/api/schema";
import { usageView } from "../../../shared/lib/budget";
import { formatUsd } from "../../../shared/lib/format";

type BudgetUsage = components["schemas"]["ProjectBudgetUsage"];

/** 패널 사용 요약 아래 한 줄. 사용액에는 추정과 귀속 구독료가 들어 있다. 예산이 없으면 0%가 아니라 미설정이다. */
export function projectUsageText(
  budget: Pick<BudgetUsage, "used_usd" | "usage_pct" | "status">,
): string {
  const usage = usageView(budget);
  const share =
    usage.status === "unset" ? "예산 미설정" : `예산의 ${usage.percent}%`;
  return `사용액 ${formatUsd(budget.used_usd, "summary")} USD (추정 포함) · ${share}`;
}

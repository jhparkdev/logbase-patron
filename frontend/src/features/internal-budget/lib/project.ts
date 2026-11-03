import type { components } from "../../../shared/api/schema";
import { usageView } from "../../../shared/lib/budget";
import { formatUsd, isZeroAmount } from "../../../shared/lib/format";

type Detail = components["schemas"]["ProjectUsageDetail"];
type BudgetUsage = components["schemas"]["ProjectBudgetUsage"];
type Breakdown = Pick<
  Detail,
  "confirmed_cost_usd" | "estimated_cost_usd" | "subscription_usd"
>;

const FULL_PERCENT = 100;
const UNSET_LABEL = "예산 미설정";

export type CostKey = "confirmed" | "estimated" | "subscription";

const COST_LABELS: Record<CostKey, string> = {
  confirmed: "API 확정 비용",
  estimated: "API 추정 비용",
  subscription: "귀속 구독료",
};

/** 요약 카드 막대 아래 왼쪽 글자. 예산이 없으면 0%가 아니라 미설정 */
export function usageHeadline(
  budget: Pick<BudgetUsage, "status" | "usage_pct">,
): string {
  const usage = usageView(budget);
  return usage.status === "unset" ? UNSET_LABEL : `${usage.percent}% 사용`;
}

/**
 * 쌓은 막대의 구간 너비(%). 각 구간은 서버가 준 금액을 예산으로 나눈 값이고 화면에서 금액을 더하지 않는다.
 * 앞 구간부터 채우고 합이 100%를 넘으면 뒤 구간을 줄인다. 예산이 없으면 막대를 그리지 않는다
 */
export function budgetSegments(
  detail: Breakdown & {
    budget: Pick<BudgetUsage, "monthly_amount_usd">;
  },
): { key: CostKey; width: number }[] | undefined {
  const monthly = detail.budget.monthly_amount_usd;
  if (monthly === null) {
    return undefined;
  }
  const amounts: [CostKey, string][] = [
    ["confirmed", detail.confirmed_cost_usd],
    ["estimated", detail.estimated_cost_usd],
    ["subscription", detail.subscription_usd],
  ];
  let room = FULL_PERCENT;
  return amounts.map(([key, amount]) => {
    const width = Math.min(
      (Number(amount) / Number(monthly)) * FULL_PERCENT,
      room,
    );
    room -= width;
    return { key, width };
  });
}

/** 사용액을 구성하는 세 금액. 서버 값 그대로이고 추정에만 ≈를 붙인다 */
export function costBreakdown(
  detail: Breakdown,
): { key: CostKey; label: string; amount: string }[] {
  const estimated = formatUsd(detail.estimated_cost_usd, "summary");
  return [
    {
      key: "confirmed",
      label: COST_LABELS.confirmed,
      amount: formatUsd(detail.confirmed_cost_usd, "summary"),
    },
    {
      key: "estimated",
      label: COST_LABELS.estimated,
      amount: isZeroAmount(detail.estimated_cost_usd)
        ? estimated
        : `≈ ${estimated}`,
    },
    {
      key: "subscription",
      label: COST_LABELS.subscription,
      amount: formatUsd(detail.subscription_usd, "summary"),
    },
  ];
}

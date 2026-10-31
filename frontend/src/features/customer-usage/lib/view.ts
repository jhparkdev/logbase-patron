import type { components } from "../../../shared/api/schema";
import type { CostAmountView } from "../../../shared/components/ui/CostAmount";
import type { UsageView } from "../../../shared/components/ui/UsageBar";

type Schemas = components["schemas"];
type RequestRow = Schemas["CustomerRequestRow"];
type BudgetStatus = Schemas["BudgetStatus"];
type RequestStatus = Schemas["RequestStatus"];

/** 호출 1건의 비용을 표시용으로 바꾼다. 미확인은 금액이 없다. */
export function costView(
  row: Pick<RequestRow, "cost_status" | "cost_usd">,
): CostAmountView {
  if (row.cost_status === "UNKNOWN" || row.cost_usd === null) {
    return { kind: "unknown", amount: null };
  }
  return {
    kind: row.cost_status === "CONFIRMED" ? "confirmed" : "estimated",
    amount: row.cost_usd,
  };
}

const USAGE_STATUS = {
  NORMAL: "normal",
  WARNING: "warning",
  OVER: "over",
} as const;

/** 상태는 서버 판정을 그대로 쓴다. 사용률은 막대와 글자에만 쓰므로 정수로 바꾼다. */
export function usageView(
  budget: Pick<Schemas["BudgetUsage"], "status" | "usage_pct">,
): UsageView {
  if (budget.status === "UNSET" || budget.usage_pct === null) {
    return { status: "unset" };
  }
  return {
    status: USAGE_STATUS[budget.status],
    percent: Math.round(Number(budget.usage_pct)),
  };
}

const BUDGET_STATUS_BADGE = {
  NORMAL: { label: "정상", tone: "green" },
  WARNING: { label: "주의", tone: "yellow" },
  OVER: { label: "초과", tone: "red" },
  UNSET: { label: "미설정", tone: "grey" },
} as const;

export function budgetStatusBadge(status: BudgetStatus) {
  return BUDGET_STATUS_BADGE[status];
}

const EXECUTION_STATUS = {
  PENDING: { label: "대기", dotClass: "bg-grey-400" },
  RUNNING: { label: "실행 중", dotClass: "bg-grey-400" },
  SUCCESS: { label: "성공", dotClass: "bg-green-500" },
  FAILED: { label: "실패", dotClass: "bg-red-500" },
  TIMEOUT: { label: "Timeout", dotClass: "bg-yellow-800" },
  CANCELLED: { label: "취소", dotClass: "bg-grey-400" },
} as const;

export function executionStatus(status: RequestStatus) {
  return EXECUTION_STATUS[status];
}

/** 요약 카드의 증감. 비교할 값이 없거나 반올림해 0%면 보여 주지 않는다. */
export function summaryTrend(changePct: string | null) {
  if (changePct === null) {
    return undefined;
  }
  const change = Number(changePct);
  const rate = Math.abs(Math.round(change));
  if (rate === 0) {
    return undefined;
  }
  return {
    direction: change > 0 ? ("up" as const) : ("down" as const),
    rate: `${rate}%`,
  };
}

export function trendDayLabel(date: string): string {
  return date.slice(5);
}

/** 막대 높이를 정하려면 숫자가 필요하다. 합산하지 않고, 글자로 보여 줄 때는 원래 문자열을 쓴다. */
export function trendPoint(point: Schemas["UsageTrendPoint"]) {
  return {
    day: trendDayLabel(point.date),
    date: point.date,
    tasks: point.task_count,
    confirmed: Number(point.confirmed_cost_usd),
    estimated: Number(point.estimated_cost_usd),
    confirmedText: point.confirmed_cost_usd,
    estimatedText: point.estimated_cost_usd,
    unknownCount: point.unknown_cost_count,
  };
}

export type TrendPointView = ReturnType<typeof trendPoint>;

export function unreflectedText(unknownCount: number): string | undefined {
  return unknownCount > 0 ? `미확인 ${unknownCount}건 미반영` : undefined;
}

/** 서버의 긴 소수("1.970000000000000000")를 입력 칸에 넣기 좋게 뒤쪽 0만 지운다. */
export function amountForInput(amount: string | null): string {
  if (amount === null) {
    return "";
  }
  return amount.includes(".") ? amount.replace(/\.?0+$/, "") : amount;
}

const ZERO_AMOUNT = /^0+(\.0+)?$/;

export function isZeroAmount(amount: string): boolean {
  return ZERO_AMOUNT.test(amount);
}

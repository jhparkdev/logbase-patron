import { z } from "zod";
import type { components } from "../api/schema";
import type { UsageView } from "../components/ui/UsageBar";
import { monthField, usdAmountField } from "./formFields";
import type { Period } from "./period";

type Schemas = components["schemas"];

const ZERO = /^-?0+(\.0+)?$/;

/** 월 예산 입력. 고객 예산(P-01)과 프로젝트 예산(P-02)이 같은 budgets 테이블이라 규칙이 같다. */
export const budgetFormSchema = z.object({
  amount: usdAmountField("월 예산을 입력해 주세요.").refine(
    (value) => !value.startsWith("-") && !ZERO.test(value),
    "월 예산은 0보다 커야 해요.",
  ),
  /** 한 번 정하면 다음 달에도 그대로 적용된다. */
  effectiveFrom: monthField("적용 시작 월을 골라 주세요."),
});

export type BudgetFormValues = z.output<typeof budgetFormSchema>;

/** 예산은 월 단위라, 조회 기간 종료일이 속한 달("YYYY-MM")의 예산과 비교한다. */
export function budgetMonthOf({ to }: Period): string {
  return to.slice(0, 7);
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

export const budgetStatusSchema = z.custom<Schemas["BudgetStatus"]>(
  (value) =>
    typeof value === "string" && Object.hasOwn(BUDGET_STATUS_BADGE, value),
);

export function budgetStatusBadge(status: Schemas["BudgetStatus"]) {
  return BUDGET_STATUS_BADGE[status];
}

/** 서버의 긴 소수("1.970000000000000000")를 입력 칸에 넣기 좋게 뒤쪽 0만 지운다. */
export function amountForInput(amount: string | null): string {
  if (amount === null) {
    return "";
  }
  return amount.includes(".") ? amount.replace(/\.?0+$/, "") : amount;
}

/** 요약 카드의 남은 예산 줄. 예산이 없으면 두지 않고, 넘었으면 음수 대신 초과 금액으로 보여 준다. */
export function remainingBudget(remaining: string | null) {
  if (remaining === null) {
    return undefined;
  }
  return remaining.startsWith("-")
    ? { label: "초과 금액", amount: remaining.slice(1), over: true }
    : { label: "남은 예산", amount: remaining, over: false };
}

const FULL_PERCENT = 100;

/** 서비스가 고객·프로젝트 예산에서 차지하는 비중. 글자는 실제 비중, 막대는 100%에서 멈춘다. */
export function serviceBudgetShare(sharePct: string | null): {
  label: string;
  percent?: number;
  width?: number;
} {
  if (sharePct === null) {
    return { label: "예산 미설정" };
  }
  const percent = Math.round(Number(sharePct));
  return {
    label: `예산의 ${percent}%`,
    percent,
    width: Math.min(percent, FULL_PERCENT),
  };
}

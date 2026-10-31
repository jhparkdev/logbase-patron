import {
  currentMonthPeriod,
  type Period,
  periodSchema,
} from "../../../shared/lib/period";

/** 주소의 조회 조건은 외부 입력이라 검증한다. 기간이 없거나 잘못되면 KST 이번 달로 본다. */
export function parseBudgetSearch(
  raw: Record<string, unknown>,
  now: Date,
): Period {
  const period = periodSchema.safeParse({ from: raw.from, to: raw.to });
  return period.success ? period.data : currentMonthPeriod(now);
}

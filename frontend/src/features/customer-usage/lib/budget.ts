import type { Period } from "../../../shared/lib/period";

/** 예산은 월 단위라, 조회 기간 종료일이 속한 달("YYYY-MM")의 예산과 비교한다. */
export function budgetMonthOf({ to }: Period): string {
  return to.slice(0, 7);
}

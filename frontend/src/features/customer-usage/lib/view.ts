import type { components } from "../../../shared/api/schema";

type Schemas = components["schemas"];

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

/** 서버의 긴 소수("1.970000000000000000")를 입력 칸에 넣기 좋게 뒤쪽 0만 지운다. */
export function amountForInput(amount: string | null): string {
  if (amount === null) {
    return "";
  }
  return amount.includes(".") ? amount.replace(/\.?0+$/, "") : amount;
}

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

/** OpenRouter 모델 ID("openai/gpt-4o")를 연하게 보여 줄 제공사와 굵게 보여 줄 이름으로 나눈다. */
export function modelName(modelId: string): {
  provider?: string;
  name: string;
} {
  const slash = modelId.indexOf("/");
  if (slash === -1) {
    return { name: modelId };
  }
  return {
    provider: modelId.slice(0, slash),
    name: modelId.slice(slash + 1),
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

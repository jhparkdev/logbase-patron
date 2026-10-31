import { z } from "zod";
import {
  currentMonthPeriod,
  type Period,
  periodSchema,
} from "../../../shared/lib/period";

/** 전체보기로 펼치는 목록과, 목록마다 정렬할 수 있는 칸(표의 칸 key와 같다) */
export const BUDGET_LIST_SORTS = {
  projects: ["project", "budget", "used", "usage", "status"],
  subscriptions: ["tool", "month", "amount", "project", "status"],
  requests: [
    "requestedAt",
    "project",
    "model",
    "tokens",
    "cost",
    "origin",
    "status",
  ],
} as const;

export type BudgetListView = keyof typeof BUDGET_LIST_SORTS;

export type BudgetSearch = Period & {
  /** 없으면 요약 화면, 있으면 그 목록의 전체보기 */
  view?: BudgetListView;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
};

const orderSchema = z.enum(["asc", "desc"]);
const pageSchema = z.number().int().min(1);

function isListView(value: unknown): value is BudgetListView {
  return typeof value === "string" && Object.hasOwn(BUDGET_LIST_SORTS, value);
}

/**
 * 주소의 조회 조건은 외부 입력이라 검증한다. 기간이 없거나 잘못되면 KST 이번 달로 본다.
 * 정렬과 페이지는 전체 목록에서만 쓰고, 허용하지 않는 값은 버린다.
 */
export function parseBudgetSearch(
  raw: Record<string, unknown>,
  now: Date,
): BudgetSearch {
  const parsedPeriod = periodSchema.safeParse({ from: raw.from, to: raw.to });
  const period = parsedPeriod.success
    ? parsedPeriod.data
    : currentMonthPeriod(now);

  if (!isListView(raw.view)) {
    return period;
  }
  const view = raw.view;
  const sortKeys: readonly string[] = BUDGET_LIST_SORTS[view];
  const sort =
    typeof raw.sort === "string" && sortKeys.includes(raw.sort)
      ? raw.sort
      : undefined;
  const order = orderSchema.safeParse(raw.order).data;
  return {
    ...period,
    view,
    // 정렬은 칸과 방향이 함께 있을 때만 쓴다.
    ...(sort !== undefined && order !== undefined && { sort, order }),
    page: pageSchema.safeParse(raw.page).data,
  };
}

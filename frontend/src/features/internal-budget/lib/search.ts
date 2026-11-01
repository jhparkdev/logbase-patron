import { z } from "zod";
import {
  currentMonthPeriod,
  type Period,
  periodSchema,
} from "../../../shared/lib/period";
import type { SortState } from "../../../shared/lib/sort";

/** 정렬할 수 있는 목록 표와, 표마다 정렬할 수 있는 칸(표의 칸 key와 같다) */
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

type Order = SortState["direction"];

export type BudgetSearch = Period & {
  /** 없으면 요약 화면, 있으면 그 목록의 전체보기 */
  view?: BudgetListView;
  /** 전체보기에서만 쓴다. */
  page?: number;
  /** 상세 패널을 연 프로젝트 번호(projects.project_id) */
  project?: number;
  /** "new"면 구독료 등록 패널을 연다. */
  subscription?: "new";
  // 정렬은 표마다 따로 둔다. 같은 표면 요약 화면과 전체보기에서 정렬이 이어진다.
  projectsSort?: string;
  projectsOrder?: Order;
  subscriptionsSort?: string;
  subscriptionsOrder?: Order;
  requestsSort?: string;
  requestsOrder?: Order;
};

const SORT_PARAMS = {
  projects: { sort: "projectsSort", order: "projectsOrder" },
  subscriptions: { sort: "subscriptionsSort", order: "subscriptionsOrder" },
  requests: { sort: "requestsSort", order: "requestsOrder" },
} as const satisfies Record<
  BudgetListView,
  { sort: keyof BudgetSearch; order: keyof BudgetSearch }
>;

const orderSchema = z.enum(["asc", "desc"]);
const positiveIntSchema = z.number().int().min(1);

function isListView(value: unknown): value is BudgetListView {
  return typeof value === "string" && Object.hasOwn(BUDGET_LIST_SORTS, value);
}

/** 그 표의 지금 정렬. 칸과 방향이 함께 있을 때만 정렬로 본다. */
export function listSortOf(
  search: BudgetSearch,
  view: BudgetListView,
): SortState | undefined {
  const key = search[SORT_PARAMS[view].sort];
  const direction = search[SORT_PARAMS[view].order];
  return key && direction ? { key, direction } : undefined;
}

/** 그 표의 정렬을 주소 값으로 바꾼다. */
export function listSortParams(
  view: BudgetListView,
  { key, direction }: SortState,
): Partial<BudgetSearch> {
  switch (view) {
    case "projects":
      return { projectsSort: key, projectsOrder: direction };
    case "subscriptions":
      return { subscriptionsSort: key, subscriptionsOrder: direction };
    case "requests":
      return { requestsSort: key, requestsOrder: direction };
  }
}

function parseListSort(
  raw: Record<string, unknown>,
  view: BudgetListView,
): Partial<BudgetSearch> {
  const key = raw[SORT_PARAMS[view].sort];
  const direction = orderSchema.safeParse(raw[SORT_PARAMS[view].order]).data;
  const allowed: readonly string[] = BUDGET_LIST_SORTS[view];
  return typeof key === "string" &&
    allowed.includes(key) &&
    direction !== undefined
    ? listSortParams(view, { key, direction })
    : {};
}

/**
 * 주소의 조회 조건은 외부 입력이라 검증한다. 기간이 없거나 잘못되면 KST 이번 달로 본다.
 * 허용하지 않는 값은 버린다. 페이지는 전체보기에서만 쓴다.
 */
export function parseBudgetSearch(
  raw: Record<string, unknown>,
  now: Date,
): BudgetSearch {
  const parsedPeriod = periodSchema.safeParse({ from: raw.from, to: raw.to });
  const search: BudgetSearch = {
    ...(parsedPeriod.success ? parsedPeriod.data : currentMonthPeriod(now)),
    ...parseListSort(raw, "projects"),
    ...parseListSort(raw, "subscriptions"),
    ...parseListSort(raw, "requests"),
    // 상세 패널은 요약 화면과 전체보기 어디서든 연다.
    project: positiveIntSchema.safeParse(raw.project).data,
    subscription: raw.subscription === "new" ? "new" : undefined,
  };
  if (!isListView(raw.view)) {
    return search;
  }
  return {
    ...search,
    view: raw.view,
    page: positiveIntSchema.safeParse(raw.page).data,
  };
}

/** 주소의 조회 기간을 내부 비용 API의 조회 조건으로 바꾼다. */
export function internalFilterQuery({ from, to }: Period) {
  return { start_date: from, end_date: to };
}

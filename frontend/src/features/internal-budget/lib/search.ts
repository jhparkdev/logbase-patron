import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import { budgetMonthOf, budgetStatusSchema } from "../../../shared/lib/budget";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import {
  currentMonthPeriod,
  type Period,
  periodSchema,
} from "../../../shared/lib/period";
import type { SortState } from "../../../shared/lib/sort";

type Schemas = components["schemas"];

/** 전체보기로 펼칠 수 있는 목록 표 */
const LIST_VIEWS = ["projects", "subscriptions", "requests"] as const;

export type BudgetListView = (typeof LIST_VIEWS)[number];

/** 표마다 정렬할 수 있는 칸(표의 칸 key와 같다). 목록 표가 빠지거나 남으면 타입 검사에서 잡힌다. */
export const BUDGET_LIST_SORTS = {
  // 백엔드 정렬 허용 목록에 없는 값을 쓰면 타입 검사에서 잡힌다.
  projects: [
    "project",
    "budget",
    "used",
    "usage",
    "status",
  ] as const satisfies readonly Schemas["ProjectRowSort"][],
  subscriptions: [
    "tool",
    "month",
    "amount",
    "project",
    "status",
  ] as const satisfies readonly Schemas["SubscriptionSort"][],
  requests: [
    "requestedAt",
    "project",
    "model",
    "tokens",
    "cost",
    "origin",
    "status",
  ] as const satisfies readonly Schemas["InternalRequestSort"][],
} as const satisfies Record<BudgetListView, readonly string[]>;

const order = z.enum(["asc", "desc"]).optional().catch(undefined);
const positiveInt = z.number().int().min(1).optional().catch(undefined);

function sortKey<View extends BudgetListView>(view: View) {
  return z.enum(BUDGET_LIST_SORTS[view]).optional().catch(undefined);
}

/**
 * 주소의 조회 조건은 외부 입력이라 검증한다. 허용하지 않는 값은 버린다.
 * 기간이 없거나 잘못되면, 주소를 읽을 때의 시각으로 KST 이번 달을 정한다.
 */
export const budgetSearchSchema = z
  .object({
    // 날짜 형식과 기간 규칙은 시작일·종료일을 함께 봐야 해서 아래에서 검사한다.
    from: z.string().optional().catch(undefined),
    to: z.string().optional().catch(undefined),
    /** 없으면 요약 화면, 있으면 그 목록의 전체보기 */
    view: z.enum(LIST_VIEWS).optional().catch(undefined),
    /** 전체보기에서만 쓴다. */
    page: positiveInt,
    /** 조회 조건. 없으면 전체다. 상세 패널의 "이 프로젝트 사용 내역 보기"도 project를 건다. */
    project: positiveInt,
    model: positiveInt,
    budgetStatus: budgetStatusSchema.optional().catch(undefined),
    /** 상세 패널을 연 프로젝트 번호(projects.project_id). 요약 화면과 전체보기 어디서든 연다. */
    detail: positiveInt,
    /** "new"면 구독료 등록 패널, 번호면 그 구독료의 수정 패널을 연다. */
    subscription: z
      .union([z.literal("new"), z.number().int().min(1)])
      .optional()
      .catch(undefined),
    // 정렬은 표마다 따로 둔다. 같은 표면 요약 화면과 전체보기에서 정렬이 이어진다.
    projectsSort: sortKey("projects"),
    projectsOrder: order,
    subscriptionsSort: sortKey("subscriptions"),
    subscriptionsOrder: order,
    requestsSort: sortKey("requests"),
    requestsOrder: order,
  })
  .transform(({ from, to, view, page, ...rest }) => {
    const period = periodSchema.safeParse({ from, to });
    return {
      ...(period.success ? period.data : currentMonthPeriod(new Date())),
      ...rest,
      ...(view === undefined ? {} : { view, page }),
    };
  });

export type BudgetSearch = z.output<typeof budgetSearchSchema>;

const SORT_PARAMS = {
  projects: { sort: "projectsSort", order: "projectsOrder" },
  subscriptions: { sort: "subscriptionsSort", order: "subscriptionsOrder" },
  requests: { sort: "requestsSort", order: "requestsOrder" },
} as const satisfies Record<
  BudgetListView,
  { sort: keyof BudgetSearch; order: keyof BudgetSearch }
>;

/** 그 표의 지금 정렬. 칸과 방향이 함께 있을 때만 정렬로 본다. */
export function listSortOf(
  search: BudgetSearch,
  view: BudgetListView,
): SortState | undefined {
  const key = search[SORT_PARAMS[view].sort];
  const direction = search[SORT_PARAMS[view].order];
  return key && direction ? { key, direction } : undefined;
}

/** 그 표의 정렬을 주소 값으로 바꾼다. 칸 key는 표의 칸 정의가 허용 목록 안의 값만 쓴다. */
export function listSortParams(
  view: BudgetListView,
  { key, direction }: SortState,
): Partial<BudgetSearch> {
  return {
    [SORT_PARAMS[view].sort]: key,
    [SORT_PARAMS[view].order]: direction,
  };
}

/** 화면 전체에 걸리는 조회 조건. 기간은 항상 있고 프로젝트·모델은 고르지 않으면 전체다. */
export type BudgetFilter = Pick<
  BudgetSearch,
  "from" | "to" | "project" | "model"
>;

/** 조회 조건 폼. 선택 상자의 "전체"는 빈 문자열이다. 기간 규칙은 조회를 누를 때 검사한다. */
export const budgetFilterFormSchema = periodSchema.and(
  z.object({ project: z.string(), model: z.string() }),
);

export type BudgetFilterForm = z.output<typeof budgetFilterFormSchema>;

function idText(id: number | undefined): string {
  return id === undefined ? "" : String(id);
}

function idOf(text: string): number | undefined {
  return text === "" ? undefined : Number(text);
}

/** 주소의 조건을 폼 값으로 바꾼다. */
export function filterFormValues(search: BudgetFilter): BudgetFilterForm {
  return {
    from: search.from,
    to: search.to,
    project: idText(search.project),
    model: idText(search.model),
  };
}

/** 조회를 눌렀을 때 주소에 남길 값. 조건이 바뀌면 1페이지로 돌아간다. */
export function filterSearchParams(values: BudgetFilterForm) {
  return {
    from: values.from,
    to: values.to,
    project: idOf(values.project),
    model: idOf(values.model),
    page: undefined,
  };
}

function periodQuery({ from, to }: Period) {
  return { start_date: from, end_date: to };
}

/** 주소의 조회 조건을 내부 비용 API의 조회 조건으로 바꾼다. 요약·프로젝트 표·이력이 함께 쓴다. */
export function internalFilterQuery(filter: BudgetFilter) {
  return {
    ...periodQuery(filter),
    project_id: filter.project,
    model_id: filter.model,
  };
}

/** 요약 화면은 미리보기(서버가 정한 N건 안에서 정렬), 그 목록의 전체보기는 페이지를 나눠 요청한다. */
function listPageQuery(search: BudgetSearch, view: BudgetListView) {
  const fullView = search.view === view;
  return {
    preview: !fullView,
    ...(fullView ? { page: search.page ?? 1, page_size: PAGE_SIZE } : {}),
  };
}

/**
 * 프로젝트 표 요청 조건. 예산은 월 단위라 조회 기간 종료일의 달과 비교한다.
 * 정렬을 고르지 않았으면 보내지 않고 서버 기본 정렬을 따른다.
 */
export function projectRowsQuery(search: BudgetSearch) {
  const { projectsSort: sort, projectsOrder: order } = search;
  return {
    month: budgetMonthOf(search),
    project_id: search.project,
    model_id: search.model,
    ...(search.budgetStatus ? { budget_status: search.budgetStatus } : {}),
    ...listPageQuery(search, "projects"),
    ...(sort && order ? { sort, order } : {}),
  };
}

/** 이력 표 요청 조건. 정렬을 고르지 않았으면 보내지 않고 서버 기본 정렬(최신순)을 따른다. */
export function requestRowsQuery(search: BudgetSearch) {
  const { requestsSort: sort, requestsOrder: order } = search;
  return {
    ...internalFilterQuery(search),
    ...listPageQuery(search, "requests"),
    ...(sort && order ? { sort, order } : {}),
  };
}

/**
 * 구독료 표 요청 조건. 조회 기간이 걸치는 모든 달을 받아 요약의 구독료 합계와 같은 조건이다.
 * 구독료는 모델과 관계없어 모델 조건은 보내지 않는다(요약은 모델 조건이면 구독료를 뺀다).
 */
export function subscriptionRowsQuery(search: BudgetSearch) {
  const { subscriptionsSort: sort, subscriptionsOrder: order } = search;
  return {
    ...periodQuery(search),
    project_id: search.project,
    ...listPageQuery(search, "subscriptions"),
    ...(sort && order ? { sort, order } : {}),
  };
}

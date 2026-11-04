import { z } from "zod";
import { budgetStatusSchema } from "../../../shared/lib/budget";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import {
  type Period,
  periodSchema,
  recentPeriod,
} from "../../../shared/lib/period";
import type { SortState } from "../../../shared/lib/sort";

/** 기획서의 시연 흐름("최근 30일 조회")과 같은 기본 조회 기간 */
const DEFAULT_PERIOD_DAYS = 30;

// 값은 백엔드 정렬 허용 목록(schemas/usage.py)과 같다. 호출 표의 costStatus는 칸을 빼서 받지 않는다.
const CUSTOMER_SORTS = [
  "customer",
  "service",
  "tasks",
  "calls",
  "confirmed",
  "estimated",
  "budget",
  "usage",
  "status",
] as const;
const REQUEST_SORTS = [
  "requestedAt",
  "customer",
  "service",
  "model",
  "taskType",
  "tokens",
  "cost",
  "status",
] as const;
const ORDERS = ["asc", "desc"] as const;

/** 머리글을 누르기 전의 정렬. 주소에 남기지 않는다. */
const DEFAULT_CUSTOMER_SORT = {
  key: "confirmed",
  direction: "desc",
} satisfies SortState;
const DEFAULT_REQUEST_SORT = {
  key: "requestedAt",
  direction: "desc",
} satisfies SortState;

const positiveId = z.number().int().min(1).optional().catch(undefined);

/**
 * 주소의 조회 조건은 외부 입력이라 검증한다. 허용하지 않는 값은 버린다.
 * 기간이 없거나 잘못되면, 주소를 읽을 때의 시각으로 KST 최근 30일을 정한다.
 */
export const customerUsageSearchSchema = z
  .object({
    // 문자열이 아닌 값은 여기서 버려 화면이 검증 오류로 멈추지 않게 한다.
    // 날짜 형식과 기간 규칙은 시작일·종료일을 함께 봐야 해서 아래에서 검사한다.
    from: z.string().optional().catch(undefined),
    to: z.string().optional().catch(undefined),
    /** 없으면 요약 화면, 있으면 그 목록의 전체보기 */
    view: z.enum(["customers", "requests"]).optional().catch(undefined),
    /** 상세 패널을 연 고객 번호(customers.customer_id). 요약 화면과 전체보기 어디서든 연다. */
    detail: positiveId,
    customer: positiveId,
    service: positiveId,
    model: positiveId,
    budgetStatus: budgetStatusSchema.optional().catch(undefined),
    customersSort: z.enum(CUSTOMER_SORTS).optional().catch(undefined),
    customersOrder: z.enum(ORDERS).optional().catch(undefined),
    requestsSort: z.enum(REQUEST_SORTS).optional().catch(undefined),
    requestsOrder: z.enum(ORDERS).optional().catch(undefined),
    /** 전체보기 페이지 */
    page: positiveId,
  })
  .transform(({ from, to, ...rest }) => {
    const period = periodSchema.safeParse({ from, to });
    return {
      ...(period.success
        ? period.data
        : recentPeriod(new Date(), DEFAULT_PERIOD_DAYS)),
      ...rest,
    };
  });

export type CustomerUsageSearch = z.output<typeof customerUsageSearchSchema>;

/** 전체보기로 펼칠 수 있는 목록 */
export type UsageListView = NonNullable<CustomerUsageSearch["view"]>;

/** 조회 조건 폼. 선택 상자의 "전체"는 빈 문자열이다. 기간 규칙은 조회를 누를 때 검사한다. */
export const usageFilterFormSchema = periodSchema.and(
  z.object({ customer: z.string(), service: z.string(), model: z.string() }),
);

export type UsageFilterForm = z.output<typeof usageFilterFormSchema>;

function idText(id: number | undefined): string {
  return id === undefined ? "" : String(id);
}

function idOf(text: string): number | undefined {
  return text === "" ? undefined : Number(text);
}

export function filterFormValues(
  search: CustomerUsageSearch,
): UsageFilterForm & Period {
  return {
    from: search.from,
    to: search.to,
    customer: idText(search.customer),
    service: idText(search.service),
    model: idText(search.model),
  };
}

/** 조회를 눌렀을 때 주소에 남길 값. 조건이 바뀌면 1페이지로 돌아간다. */
export function filterSearchParams(values: UsageFilterForm) {
  return {
    from: values.from,
    to: values.to,
    customer: idOf(values.customer),
    service: idOf(values.service),
    model: idOf(values.model),
    page: undefined,
  };
}

/** 네 블록이 함께 쓰는 API 조회 조건. */
export function usageFilterQuery(search: CustomerUsageSearch) {
  return {
    start_date: search.from,
    end_date: search.to,
    customer_id: search.customer,
    service_id: search.service,
    model_id: search.model,
  };
}

function listQuery(search: CustomerUsageSearch, view: UsageListView) {
  const fullView = search.view === view;
  return {
    ...usageFilterQuery(search),
    preview: !fullView,
    ...(fullView ? { page: search.page ?? 1, page_size: PAGE_SIZE } : {}),
  };
}

export function customerSortOf(search: CustomerUsageSearch): SortState {
  return search.customersSort === undefined
    ? DEFAULT_CUSTOMER_SORT
    : {
        key: search.customersSort,
        direction: search.customersOrder ?? "desc",
      };
}

export function requestSortOf(search: CustomerUsageSearch): SortState {
  return search.requestsSort === undefined
    ? DEFAULT_REQUEST_SORT
    : { key: search.requestsSort, direction: search.requestsOrder ?? "desc" };
}

export function customerRowsQuery(search: CustomerUsageSearch) {
  return {
    ...listQuery(search, "customers"),
    sort: search.customersSort ?? "confirmed",
    order: customerSortOf(search).direction,
    ...(search.budgetStatus ? { budget_status: search.budgetStatus } : {}),
  };
}

export function requestRowsQuery(search: CustomerUsageSearch) {
  return {
    ...listQuery(search, "requests"),
    sort: search.requestsSort ?? "requestedAt",
    order: requestSortOf(search).direction,
  };
}

/** 표마다 정렬을 따로 둔다. 정렬이 바뀌면 1페이지로 돌아간다. */
export function customerSortParams(sort: SortState) {
  return {
    customersSort: sort.key as (typeof CUSTOMER_SORTS)[number],
    customersOrder: sort.direction,
    page: undefined,
  };
}

export function requestSortParams(sort: SortState) {
  return {
    requestsSort: sort.key as (typeof REQUEST_SORTS)[number],
    requestsOrder: sort.direction,
    page: undefined,
  };
}

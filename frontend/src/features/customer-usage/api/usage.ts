import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import {
  type CustomerUsageSearch,
  customerRowsQuery,
  requestRowsQuery,
  usageFilterQuery,
} from "../lib/search";

export type CustomerUsageRow = components["schemas"]["CustomerUsageRow"];
export type CustomerRequestRow = components["schemas"]["CustomerRequestRow"];
type BudgetSave = components["schemas"]["CustomerBudgetSave"];

const ROOT_KEY = "customer-usage";
/** 호출 기록은 계속 쌓이지만 조회 버튼으로 다시 보는 화면이라 잠깐은 캐시를 쓴다. */
const USAGE_STALE_TIME_MS = 30_000;
/** 고객·서비스 목록은 거의 바뀌지 않는다. */
const OPTIONS_STALE_TIME_MS = 5 * 60_000;

export const usageOptionsQuery = queryOptions({
  queryKey: [ROOT_KEY, "options"],
  queryFn: async () => unwrap(await api.GET("/api/usage/customers/options")),
  staleTime: OPTIONS_STALE_TIME_MS,
  retry: false,
});

export function usageSummaryQuery(search: CustomerUsageSearch) {
  const query = usageFilterQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "summary", query],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/customers/summary", { params: { query } }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function usageTrendQuery(search: CustomerUsageSearch) {
  const query = usageFilterQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "trend", query],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/customers/trend", { params: { query } }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function customerRowsOptions(search: CustomerUsageSearch) {
  const query = customerRowsQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "rows", query],
    queryFn: async () =>
      unwrap(await api.GET("/api/usage/customers/rows", { params: { query } })),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function requestRowsOptions(search: CustomerUsageSearch) {
  const query = requestRowsQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "requests", query],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/customers/requests", { params: { query } }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function customerDetailQuery(customerId: number, month: string) {
  return queryOptions({
    queryKey: [ROOT_KEY, "detail", customerId, month],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/customers/{customer_id}", {
          params: { path: { customer_id: customerId }, query: { month } },
        }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

/** 예산 저장 뒤 다시 불러올 키. 요약과 추이, 호출 목록은 예산과 관계없다. */
export const BUDGET_AFFECTED_KEYS = [
  [ROOT_KEY, "rows"],
  [ROOT_KEY, "detail"],
];

export async function saveCustomerBudget(customerId: number, body: BudgetSave) {
  return unwrap(
    await api.PUT("/api/usage/customers/{customer_id}/budget", {
      params: { path: { customer_id: customerId } },
      body,
    }),
  );
}

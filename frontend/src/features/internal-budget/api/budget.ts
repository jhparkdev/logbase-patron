import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import type { Period } from "../../../shared/lib/period";
import {
  type BudgetSearch,
  internalFilterQuery,
  projectRowsQuery,
  requestRowsQuery,
} from "../lib/search";

export type ProjectBudgetRow = components["schemas"]["ProjectBudgetRow"];
export type InternalRequestRow = components["schemas"]["InternalRequestRow"];

const ROOT_KEY = "internal-budget";
/** 호출 기록은 계속 쌓이지만 조회 버튼으로 다시 보는 화면이라 잠깐은 캐시를 쓴다. */
const USAGE_STALE_TIME_MS = 30_000;

export function internalSummaryQuery(period: Period) {
  const query = internalFilterQuery(period);
  return queryOptions({
    queryKey: [ROOT_KEY, "summary", query],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/internal/summary", { params: { query } }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function projectRowsOptions(search: BudgetSearch) {
  const query = projectRowsQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "projects", query],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/internal/projects", { params: { query } }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function requestRowsOptions(search: BudgetSearch) {
  const query = requestRowsQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "requests", query],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/internal/requests", { params: { query } }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

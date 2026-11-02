import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import type { Period } from "../../../shared/lib/period";
import {
  type BudgetSearch,
  internalFilterQuery,
  projectRowsQuery,
  requestRowsQuery,
  subscriptionRowsQuery,
} from "../lib/search";

export type ProjectBudgetRow = components["schemas"]["ProjectBudgetRow"];
export type InternalRequestRow = components["schemas"]["InternalRequestRow"];
export type SubscriptionRow = components["schemas"]["SubscriptionRow"];
type BudgetSave = components["schemas"]["ProjectBudgetSave"];

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

export function subscriptionRowsOptions(search: BudgetSearch) {
  const query = subscriptionRowsQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "subscriptions", query],
    queryFn: async () =>
      unwrap(await api.GET("/api/subscriptions", { params: { query } })),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

export function projectDetailQuery(projectId: number, month: string) {
  return queryOptions({
    queryKey: [ROOT_KEY, "project", projectId, month],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/usage/internal/projects/{project_id}", {
          params: { path: { project_id: projectId }, query: { month } },
        }),
      ),
    staleTime: USAGE_STALE_TIME_MS,
    retry: false,
  });
}

/** 예산 저장 뒤 다시 불러올 키. 요약 카드, 추이, 이력은 예산과 관계없다. */
export const PROJECT_BUDGET_AFFECTED_KEYS = [
  [ROOT_KEY, "projects"],
  [ROOT_KEY, "project"],
];

export async function saveProjectBudget(projectId: number, body: BudgetSave) {
  return unwrap(
    await api.PUT("/api/usage/internal/projects/{project_id}/budget", {
      params: { path: { project_id: projectId } },
      body,
    }),
  );
}

import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import {
  type BudgetFilter,
  type BudgetSearch,
  internalFilterQuery,
  projectRowsQuery,
  requestRowsQuery,
  subscriptionRowsQuery,
} from "../lib/search";

export type ProjectBudgetRow = components["schemas"]["ProjectBudgetRow"];
export type InternalRequestRow = components["schemas"]["InternalRequestRow"];
export type SubscriptionRow = components["schemas"]["SubscriptionRow"];
export type SubscriptionProject = components["schemas"]["SubscriptionProject"];
type BudgetSave = components["schemas"]["ProjectBudgetSave"];
type SubscriptionCreate = components["schemas"]["SubscriptionCreate"];
type SubscriptionUpdate = components["schemas"]["SubscriptionUpdate"];

const ROOT_KEY = "internal-budget";
/** 호출 기록은 계속 쌓이지만 조회 버튼으로 다시 보는 화면이라 잠깐은 캐시를 쓴다. */
const USAGE_STALE_TIME_MS = 30_000;
/** 프로젝트·모델 목록은 거의 바뀌지 않는다. */
const OPTIONS_STALE_TIME_MS = 5 * 60_000;

export const internalOptionsQuery = queryOptions({
  queryKey: [ROOT_KEY, "options"],
  queryFn: async () => unwrap(await api.GET("/api/usage/internal/options")),
  staleTime: OPTIONS_STALE_TIME_MS,
  retry: false,
});

/** 구독료 폼의 귀속 프로젝트 선택지 */
export const subscriptionOptionsQuery = queryOptions({
  queryKey: [ROOT_KEY, "subscription-options"],
  queryFn: async () => unwrap(await api.GET("/api/subscriptions/options")),
  staleTime: OPTIONS_STALE_TIME_MS,
  retry: false,
});

export function internalSummaryQuery(filter: BudgetFilter) {
  const query = internalFilterQuery(filter);
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

/** 구독료를 등록·수정한 뒤 다시 불러올 키. 구독료 표와 요약(월 구독료·총 관리 비용)이 바뀐다. */
export const SUBSCRIPTION_AFFECTED_KEYS = [
  [ROOT_KEY, "subscriptions"],
  [ROOT_KEY, "summary"],
];

export async function createSubscription(body: SubscriptionCreate) {
  return unwrap(await api.POST("/api/subscriptions", { body }));
}

export async function updateSubscription(
  subscriptionId: number,
  body: SubscriptionUpdate,
) {
  return unwrap(
    await api.PATCH("/api/subscriptions/{subscription_id}", {
      params: { path: { subscription_id: subscriptionId } },
      body,
    }),
  );
}

import { vi } from "vitest";
import type { components } from "../shared/api/schema";

type Schemas = components["schemas"];

const BASE = "/api/usage/internal";
const JSON_HEADERS = { "Content-Type": "application/json" };

export const SUMMARY: Schemas["InternalSummary"] = {
  api_confirmed_usd: "1240.500000000000",
  api_estimated_usd: "320.150000000000",
  subscription_usd: "980.0000",
  total_managed_usd: "2540.650000000000",
  unknown_cost_count: 3,
  includes_estimate: true,
  has_unknown: true,
};

export const PROJECTS: Schemas["ProjectBudgetPage"] = {
  items: [
    {
      project_id: 1,
      project_name: "사내 챗봇 구축",
      monthly_amount_usd: "10.0000",
      used_usd: "12.100000000000",
      usage_pct: "121.00",
      status: "OVER",
      unknown_cost_count: 2,
    },
    {
      project_id: 2,
      project_name: "문서 요약",
      monthly_amount_usd: null,
      used_usd: "0",
      usage_pct: null,
      status: "UNSET",
      unknown_cost_count: 0,
    },
  ],
  total: 12,
  page: 1,
  page_size: 10,
};

const REQUEST_BASE = {
  service_id: 10,
  service_name: "사내 챗봇",
  task_id: null,
  task_type: null,
  task_type_label: null,
  error_type: null,
} as const;

export const REQUESTS: Schemas["InternalRequestPage"] = {
  items: [
    {
      ...REQUEST_BASE,
      request_id: "00000000-0000-0000-0000-000000000001",
      requested_at: "2026-10-31T05:32:21Z",
      usage_origin: "INTERNAL_DEVELOPMENT",
      project_id: 1,
      project_name: "사내 챗봇 구축",
      model: "openai/gpt-4o",
      tokens: 125320,
      cost_usd: "0.020000000000",
      cost_status: "CONFIRMED",
      status: "SUCCESS",
    },
    {
      ...REQUEST_BASE,
      request_id: "00000000-0000-0000-0000-000000000002",
      requested_at: "2026-10-30T15:00:00Z",
      usage_origin: "SIMULATION",
      project_id: null,
      project_name: null,
      model: "anthropic/claude-sonnet",
      tokens: null,
      cost_usd: "0.080000000000",
      cost_status: "ESTIMATED",
      status: "SUCCESS",
    },
    {
      ...REQUEST_BASE,
      request_id: "00000000-0000-0000-0000-000000000003",
      requested_at: "2026-10-29T01:00:00Z",
      usage_origin: "SYSTEM_TEST",
      project_id: null,
      project_name: null,
      model: "google/gemini-pro",
      tokens: 10,
      cost_usd: null,
      cost_status: "UNKNOWN",
      status: "TIMEOUT",
      error_type: "TIMEOUT_ERROR",
    },
  ],
  total: 23,
  page: 1,
  page_size: 10,
};

export const PROJECT_DETAIL: Schemas["ProjectUsageDetail"] = {
  project_id: 1,
  project_name: "사내 챗봇 구축",
  month: "2026-10",
  task_count: 12,
  call_count: 40,
  confirmed_cost_usd: "3100.200000000000",
  estimated_cost_usd: "320.300000000000",
  subscription_usd: "0.0000",
  unknown_cost_count: 2,
  budget: {
    month: "2026-10",
    monthly_amount_usd: "5000.0000",
    effective_from_month: "2026-09",
    used_usd: "3420.500000000000",
    usage_pct: "68.41",
    confirmed_usage_pct: "62.00",
    remaining_usd: "1579.500000000000",
    unknown_cost_count: 2,
    status: "NORMAL",
  },
  services: [],
  subscriptions: [],
};

const SAVED_BUDGET: Schemas["ProjectBudgetRead"] = {
  budget_id: 9,
  project_id: 1,
  monthly_amount_usd: "6000.0000",
  effective_from_month: "2026-10",
  effective_to_month: null,
};

type Reply = { status: number; body: unknown };
function ok(body: unknown): Reply {
  return { status: 200, body };
}

const DEFAULT_REPLIES = {
  summary: ok(SUMMARY),
  projects: ok(PROJECTS),
  requests: ok(REQUESTS),
  detail: ok(PROJECT_DETAIL),
  budget: ok(SAVED_BUDGET),
};

/** 경로 끝부분별 응답을 바꾼다. 예: { summary: { status: 500, body: {} } } */
type Replies = Partial<Record<keyof typeof DEFAULT_REPLIES, Reply>>;

const PROJECT_DETAIL_PATH = /^projects\/\d+$/;
const PROJECT_BUDGET_PATH = /^projects\/\d+\/budget$/;

function blockOf(pathname: string): keyof typeof DEFAULT_REPLIES {
  const last = pathname.slice(BASE.length + 1);
  if (PROJECT_DETAIL_PATH.test(last)) {
    return "detail";
  }
  if (PROJECT_BUDGET_PATH.test(last)) {
    return "budget";
  }
  if (last in DEFAULT_REPLIES) {
    return last as keyof typeof DEFAULT_REPLIES;
  }
  // 가짜 응답을 아직 만들지 않은 API를 화면이 부르면 테스트가 바로 알 수 있게 한다.
  throw new Error(`가짜 응답이 없는 경로입니다: ${pathname}`);
}

/** 브라우저 fetch를 P-02 API 응답으로 바꾼다. 보낸 요청은 돌려준 목록에 쌓인다. */
export function stubInternalBudgetApi(initial: Replies = {}) {
  const replies: Replies = { ...initial };
  const requests: { url: URL; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    const url = new URL(request.url);
    const text = await request.clone().text();
    requests.push({
      url,
      method: request.method,
      body: text === "" ? undefined : JSON.parse(text),
    });
    const block = blockOf(url.pathname);
    const reply = replies[block] ?? DEFAULT_REPLIES[block];
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  return { requests, replies };
}

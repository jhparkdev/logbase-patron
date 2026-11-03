import { vi } from "vitest";
import type { components } from "../shared/api/schema";

type Schemas = components["schemas"];

const BASE = "/api/usage/internal";
const JSON_HEADERS = { "Content-Type": "application/json" };

export const OPTIONS: Schemas["InternalOptions"] = {
  projects: [
    { id: 1, name: "사내 챗봇 구축" },
    { id: 2, name: "문서 요약" },
  ],
  services: [{ id: 10, name: "사내 챗봇" }],
  models: [{ id: 20, name: "openai/gpt-4o" }],
};

export const SUMMARY: Schemas["InternalSummary"] = {
  api_confirmed_usd: "1240.500000000000",
  api_estimated_usd: "320.150000000000",
  subscription_usd: "980.0000",
  total_managed_usd: "2540.650000000000",
  unknown_cost_count: 3,
  includes_estimate: true,
  has_unknown: true,
  subscription_excluded: false,
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

export const SUBSCRIPTIONS: Schemas["SubscriptionList"] = {
  items: [
    {
      subscription_id: 1,
      subscription_reference: "command-code-team",
      tool_name: "Command Code",
      subscription_type: "Team",
      applied_month: "2026-10",
      amount_usd: "100.0000",
      project_id: 1,
      project_name: "사내 챗봇 구축",
      status: "ACTIVE",
      note: null,
    },
    {
      subscription_id: 2,
      subscription_reference: "notion-ai",
      tool_name: "Notion AI",
      subscription_type: null,
      applied_month: "2026-09",
      amount_usd: "20.0000",
      project_id: null,
      project_name: null,
      status: "CANCELLED",
      note: "9월에 해지",
    },
  ],
  total: 12,
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
    warning_threshold_pct: "80",
  },
  services: [],
  subscriptions: [],
};

export const SUBSCRIPTION_OPTIONS: Schemas["SubscriptionOptions"] = {
  projects: [
    { project_id: 1, name: "사내 챗봇 구축" },
    { project_id: 2, name: "문서 요약" },
  ],
};

export const PROJECT_CREATED: Schemas["ProjectRead"] = {
  project_id: 3,
  project_code: "PRJ-3",
  name: "신규 프로젝트",
  project_type: "INTERNAL_DEV",
};

export const MEMBER_USAGE: Schemas["CommandCodeUsageList"] = {
  items: [
    {
      member_name: "홍길동",
      status: "OK",
      used_credits: "27.6518301021",
      request_count: 2379,
      input_tokens: 816632167,
      output_tokens: 1987270,
      remaining_credits: "62.3745912155",
      period_start: "2026-10-20T02:04:33Z",
      period_end: "2026-11-20T02:04:33Z",
      fetched_at: "2026-11-03T01:00:00Z",
    },
    {
      member_name: "김철수",
      status: "KEY_MISSING",
      fetched_at: "2026-11-03T01:00:00Z",
    },
  ],
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
  options: ok(OPTIONS),
  summary: ok(SUMMARY),
  projects: ok(PROJECTS),
  requests: ok(REQUESTS),
  subscriptions: ok(SUBSCRIPTIONS),
  subscriptionOptions: ok(SUBSCRIPTION_OPTIONS),
  subscriptionCreate: { status: 201, body: SUBSCRIPTIONS.items[0] },
  subscription: ok(SUBSCRIPTIONS.items[1]),
  subscriptionUpdate: ok(SUBSCRIPTIONS.items[0]),
  detail: ok(PROJECT_DETAIL),
  budget: ok(SAVED_BUDGET),
  projectCreate: { status: 201, body: PROJECT_CREATED },
  commandCode: ok(MEMBER_USAGE),
};

/** 경로 끝부분별 응답을 바꾼다. 예: { summary: { status: 500, body: {} } } */
type Replies = Partial<Record<keyof typeof DEFAULT_REPLIES, Reply>>;

const SUBSCRIPTIONS_PATH = "/api/subscriptions";
const PROJECTS_PATH = "/api/projects";
const SUBSCRIPTION_PATH = /^\/api\/subscriptions\/\d+$/;
const PROJECT_DETAIL_PATH = /^projects\/\d+$/;
const PROJECT_BUDGET_PATH = /^projects\/\d+\/budget$/;

function blockOf(
  pathname: string,
  method: string,
): keyof typeof DEFAULT_REPLIES {
  if (pathname === SUBSCRIPTIONS_PATH) {
    return method === "POST" ? "subscriptionCreate" : "subscriptions";
  }
  if (pathname === `${SUBSCRIPTIONS_PATH}/options`) {
    return "subscriptionOptions";
  }
  if (pathname === PROJECTS_PATH) {
    return "projectCreate";
  }
  if (SUBSCRIPTION_PATH.test(pathname)) {
    return method === "GET" ? "subscription" : "subscriptionUpdate";
  }
  const last = pathname.slice(BASE.length + 1);
  if (PROJECT_DETAIL_PATH.test(last)) {
    return "detail";
  }
  if (PROJECT_BUDGET_PATH.test(last)) {
    return "budget";
  }
  if (last === "command-code") {
    return "commandCode";
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
    const block = blockOf(url.pathname, request.method);
    const reply = replies[block] ?? DEFAULT_REPLIES[block];
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  return { requests, replies };
}

import { vi } from "vitest";
import type { components } from "../shared/api/schema";

type Schemas = components["schemas"];

const BASE = "/api/usage/customers";
const JSON_HEADERS = { "Content-Type": "application/json" };

export const OPTIONS: Schemas["UsageOptions"] = {
  customers: [
    { id: 1, name: "A기업" },
    { id: 2, name: "B기업" },
  ],
  services: [{ id: 10, name: "AI PDP" }],
  models: [{ id: 20, name: "Kimi" }],
};

export const SUMMARY: Schemas["UsageSummary"] = {
  comparison_start_date: "2026-09-01",
  comparison_end_date: "2026-09-30",
  task_count: 1730,
  call_count: 27901,
  success_count: 27000,
  failed_count: 800,
  timeout_count: 101,
  input_tokens: 100,
  output_tokens: 50,
  confirmed_cost_usd: "147.000000000000000000",
  estimated_cost_usd: "47.000000000000000000",
  unknown_cost_count: 3,
  task_change_pct: "12.00",
  call_change_pct: "-5.00",
  confirmed_cost_change_pct: null,
  estimated_cost_change_pct: "0.00",
};

export const TREND: Schemas["UsageTrend"] = {
  items: [
    {
      date: "2026-10-01",
      task_count: 3,
      call_count: 9,
      confirmed_cost_usd: "1.50",
      estimated_cost_usd: "0.25",
      unknown_cost_count: 1,
    },
    {
      date: "2026-10-02",
      task_count: 0,
      call_count: 0,
      confirmed_cost_usd: "0",
      estimated_cost_usd: "0",
      unknown_cost_count: 0,
    },
  ],
};

const OVER_BUDGET: Schemas["BudgetUsage"] = {
  month: "2026-10",
  monthly_amount_usd: "10.000000000000000000",
  effective_from_month: "2026-09",
  used_usd: "12.10",
  usage_pct: "121.00",
  confirmed_usage_pct: "21.00",
  remaining_usd: "-2.10",
  unknown_cost_count: 2,
  status: "OVER",
  warning_threshold_pct: "80",
};

const UNSET_BUDGET: Schemas["BudgetUsage"] = {
  month: "2026-10",
  monthly_amount_usd: null,
  effective_from_month: null,
  used_usd: "1.00",
  usage_pct: null,
  confirmed_usage_pct: null,
  remaining_usd: null,
  unknown_cost_count: 0,
  status: "UNSET",
  warning_threshold_pct: "80",
};

const CUSTOMER_ROW: Schemas["CustomerUsageRow"] = {
  customer_id: 1,
  customer_name: "A기업",
  service_id: 10,
  service_name: "AI PDP",
  task_count: 98,
  call_count: 1000,
  confirmed_cost_usd: "2.10",
  estimated_cost_usd: "10.00",
  unknown_cost_count: 2,
  budget: OVER_BUDGET,
};

export const ROWS: Schemas["CustomerUsagePage"] = {
  items: [
    CUSTOMER_ROW,
    {
      ...CUSTOMER_ROW,
      customer_id: null,
      customer_name: null,
      service_id: 11,
      service_name: "FlipPage",
      budget: UNSET_BUDGET,
    },
  ],
  total: 12,
  page: 1,
  page_size: 10,
};

const REQUEST_ROW: Schemas["CustomerRequestRow"] = {
  request_id: "00000000-0000-0000-0000-000000000001",
  requested_at: "2026-10-31T05:32:21Z",
  customer_id: 1,
  customer_name: "A기업",
  service_id: 10,
  service_name: "AI PDP",
  model: "openai/gpt-4o",
  task_id: null,
  task_type: "PRODUCT_DESCRIPTION",
  task_type_label: "상품 설명 생성",
  tokens: 1245,
  cost_usd: "0.0200",
  cost_status: "CONFIRMED",
  status: "SUCCESS",
  error_type: null,
};

export const REQUESTS: Schemas["CustomerRequestPage"] = {
  items: [
    REQUEST_ROW,
    {
      ...REQUEST_ROW,
      request_id: "00000000-0000-0000-0000-000000000002",
      tokens: null,
      task_type: null,
      task_type_label: null,
      cost_usd: null,
      cost_status: "UNKNOWN",
      status: "TIMEOUT",
      error_type: "TIMEOUT_ERROR",
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
};

export const DETAIL: Schemas["CustomerUsageDetail"] = {
  customer_id: 1,
  customer_name: "A기업",
  month: "2026-10",
  task_count: 98,
  call_count: 1000,
  confirmed_cost_usd: "2.10",
  estimated_cost_usd: "10.00",
  unknown_cost_count: 2,
  budget: OVER_BUDGET,
  services: [
    {
      service_id: 10,
      service_name: "AI PDP",
      task_count: 98,
      call_count: 1000,
      confirmed_cost_usd: "2.10",
      estimated_cost_usd: "10.00",
      total_cost_usd: "12.10",
      unknown_cost_count: 2,
      budget_share_pct: "121.00",
    },
  ],
};

const SAVED_BUDGET: Schemas["CustomerBudgetRead"] = {
  budget_id: 1,
  customer_id: 1,
  monthly_amount_usd: "20",
  effective_from_month: "2026-10",
  effective_to_month: null,
};

type Reply = { status: number; body: unknown };
/** 경로 끝부분별 응답을 바꾼다. 예: { summary: { status: 500, body: {} } } */
type Replies = Partial<
  Record<
    "options" | "summary" | "trend" | "rows" | "requests" | "detail" | "budget",
    Reply
  >
>;

function ok(body: unknown): Reply {
  return { status: 200, body };
}

const DEFAULT_REPLIES = {
  options: ok(OPTIONS),
  summary: ok(SUMMARY),
  trend: ok(TREND),
  rows: ok(ROWS),
  requests: ok(REQUESTS),
  detail: ok(DETAIL),
  budget: ok(SAVED_BUDGET),
};

function blockOf(pathname: string): keyof typeof DEFAULT_REPLIES {
  const last = pathname.slice(BASE.length + 1);
  if (last.endsWith("/budget")) {
    return "budget";
  }
  if (last in DEFAULT_REPLIES) {
    return last as keyof typeof DEFAULT_REPLIES;
  }
  return "detail";
}

/** 브라우저 fetch를 P-01 API 응답으로 바꾼다. 보낸 요청은 돌려준 목록에 쌓인다. */
export function stubCustomerUsageApi(initial: Replies = {}) {
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

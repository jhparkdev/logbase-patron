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

type Reply = { status: number; body: unknown };
/** 경로 끝부분별 응답을 바꾼다. 예: { summary: { status: 500, body: {} } } */
type Replies = Partial<Record<"summary", Reply>>;

function ok(body: unknown): Reply {
  return { status: 200, body };
}

const DEFAULT_REPLIES = {
  summary: ok(SUMMARY),
};

function blockOf(pathname: string): keyof typeof DEFAULT_REPLIES {
  const last = pathname.slice(BASE.length + 1);
  if (last in DEFAULT_REPLIES) {
    return last as keyof typeof DEFAULT_REPLIES;
  }
  // 가짜 응답을 아직 만들지 않은 API를 화면이 부르면 테스트가 바로 알 수 있게 한다.
  throw new Error(`가짜 응답이 없는 경로입니다: ${pathname}`);
}

/** 브라우저 fetch를 P-02 API 응답으로 바꾼다. 보낸 요청은 돌려준 목록에 쌓인다. */
export function stubInternalBudgetApi(initial: Replies = {}) {
  const replies: Replies = { ...initial };
  const requests: { url: URL }[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    const url = new URL(request.url);
    requests.push({ url });
    const block = blockOf(url.pathname);
    const reply = replies[block] ?? DEFAULT_REPLIES[block];
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  return { requests, replies };
}

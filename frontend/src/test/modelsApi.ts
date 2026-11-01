import { vi } from "vitest";
import type { components } from "../shared/api/schema";

type Schemas = components["schemas"];

const JSON_HEADERS = { "Content-Type": "application/json" };

const PRICE: Schemas["PriceRead"] = {
  price_id: 1,
  execution_provider: null,
  currency: "USD",
  price_status: "KNOWN",
  input_price_per_token: "0.00000015",
  output_price_per_token: "0.0000025",
  cache_read_price_per_token: null,
  cache_write_price_per_token: null,
  source: "OPENROUTER_MODELS",
  effective_from: "2026-10-01T00:00:00Z",
  effective_to: null,
  checked_at: "2026-10-31T00:00:00Z",
};

export const MODEL_ROW: Schemas["ModelRead"] = {
  model_id: 3,
  openrouter_model_id: "openai/gpt-4o-mini",
  display_name: "GPT-4o mini",
  provider: "openai",
  purpose: null,
  status: "ACTIVE",
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  supports_json_schema: true,
  supports_tools: true,
  context_length: 128000,
  current_price: PRICE,
  last_test_status: "SUCCESS",
  last_test_at: "2026-10-31T05:32:21Z",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-31T05:32:21Z",
};

export const UNPRICED_ROW: Schemas["ModelRead"] = {
  ...MODEL_ROW,
  model_id: 4,
  openrouter_model_id: "mistralai/mistral-small",
  display_name: "Mistral Small",
  provider: "mistralai",
  status: "TESTING",
  input_modalities: ["text"],
  current_price: null,
  last_test_status: null,
  last_test_at: null,
};

export const LIST: Schemas["ModelListResponse"] = {
  items: [MODEL_ROW, UNPRICED_ROW],
  page: 1,
  page_size: 10,
  total: 12,
};

type Reply = { status: number; body: unknown };
type Replies = { list?: Reply };

/** 브라우저 fetch를 P-03 API 응답으로 대체. 보낸 요청은 반환된 목록에 기록 */
export function stubModelsApi(initial: Replies = {}) {
  const replies: Replies = { ...initial };
  const requests: { url: URL }[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    requests.push({ url: new URL(request.url) });
    const reply = replies.list ?? { status: 200, body: LIST };
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  return { requests, replies };
}

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
  temperature_supported: true,
  reasoning_efforts: [],
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

export const DETAIL: Schemas["ModelDetailRead"] = {
  ...MODEL_ROW,
  activated_at: "2026-10-20T01:00:00Z",
  deactivated_at: null,
  last_success_test_at: "2026-10-30T02:00:00Z",
};

/** 가격도 테스트도 활성화도 없는 막 등록한 모델 */
export const UNPRICED_DETAIL: Schemas["ModelDetailRead"] = {
  ...UNPRICED_ROW,
  activated_at: null,
  deactivated_at: null,
  last_success_test_at: null,
};

export const TEST_RESULT: Schemas["ConnectionTestResult"] = {
  status: "SUCCESS",
  tested_at: "2026-11-01T03:00:00Z",
  latency_ms: 1234,
  input_tokens: 12,
  output_tokens: 30,
  cost_usd: "0.0004",
  cost_status: "CONFIRMED",
  actual_provider: "OpenAI",
  error_type: null,
  error_message: null,
};

const OPENROUTER_BASE: Schemas["OpenRouterModelRead"] = {
  openrouter_model_id: "openai/gpt-4o",
  name: "GPT-4o",
  provider: "openai",
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  context_length: 128000,
  input_price_per_token: "0.0000025",
  output_price_per_token: "0.00001",
  supports_json_schema: true,
  supports_tools: true,
  registered: false,
  created_at: null,
};

export const OPENROUTER: Schemas["OpenRouterModelListResponse"] = {
  items: [
    OPENROUTER_BASE,
    {
      ...OPENROUTER_BASE,
      openrouter_model_id: "openai/gpt-4o-mini",
      name: "GPT-4o mini",
      registered: true,
    },
    {
      ...OPENROUTER_BASE,
      openrouter_model_id: "acme/free-model",
      name: "Free Model",
      provider: "acme",
      input_modalities: ["text"],
      context_length: 4096,
      input_price_per_token: null,
      output_price_per_token: null,
      supports_json_schema: false,
      supports_tools: false,
    },
  ],
  page: 1,
  page_size: 10,
  total: 3,
};

const NEW_MODEL_BASE: Schemas["OpenRouterNewModelRead"] = {
  openrouter_model_id: "acme/alpha",
  name: "Acme: Alpha",
  provider: "acme",
  created_at: "2026-11-02T13:29:14Z",
  input_modalities: ["text"],
  output_modalities: ["text"],
  context_length: 128000,
  input_price_per_token: "0.000001",
  output_price_per_token: "0.000002",
};

/** 새 모델 5개 중 최근 1개만 담긴 응답 */
export const NEW_MODELS: Schemas["OpenRouterNewModelsResponse"] = {
  days: 5,
  total: 5,
  items: [NEW_MODEL_BASE],
};

/** 새 모델이 없는 응답. 알림이 보이지 않는 것이 기본 상태다 */
export const NO_NEW_MODELS: Schemas["OpenRouterNewModelsResponse"] = {
  days: 5,
  total: 0,
  items: [],
};

/** 비교한 새 모델이 없는 응답. 비교 결과 구역이 보이지 않는 것이 기본 상태다 */
export const NO_DISCOVERIES: Schemas["ModelDiscoveriesResponse"] = {
  items: [],
};

/** 싸고 빠른 모델 하나와 비교하지 않고 넘어간 모델 하나 */
export const DISCOVERIES: Schemas["ModelDiscoveriesResponse"] = {
  items: [
    {
      openrouter_model_id: "acme/new",
      name: "Acme: New",
      discovered_at: "2026-11-05T01:00:00Z",
      status: "COMPARED",
      skip_reason: null,
      base_model_name: "GPT-4o mini",
      new_cost_usd: "0.0005",
      base_cost_usd: "0.001",
      new_latency_ms: 800,
      base_latency_ms: 1000,
      cost_change_pct: "-50.0",
      latency_change_pct: "-20.0",
      cheaper: true,
      faster: true,
    },
    {
      openrouter_model_id: "acme/pricey",
      name: "Acme: Pricey",
      discovered_at: "2026-11-05T00:00:00Z",
      status: "SKIPPED",
      skip_reason: "PRICE_TOO_HIGH",
      base_model_name: null,
      new_cost_usd: null,
      base_cost_usd: null,
      new_latency_ms: null,
      base_latency_ms: null,
      cost_change_pct: null,
      latency_change_pct: null,
      cheaper: null,
      faster: null,
    },
  ],
};

/** 업체 둘이 순위에 있고 하나는 가동률이 낮아 빠진 응답 */
export const RANKING: Schemas["ProviderRankingResponse"] = {
  items: [
    {
      execution_provider: "DeepInfra",
      expected_cost_usd: "0.0021",
      input_price_per_token: "0.0000005",
      output_price_per_token: "0.000002",
      cache_read_price_per_token: "0.0000001",
      cache_write_price_per_token: null,
      supports_caching: true,
    },
    {
      execution_provider: "Parasail",
      expected_cost_usd: "0.0035",
      input_price_per_token: "0.000001",
      output_price_per_token: "0.000003",
      cache_read_price_per_token: null,
      cache_write_price_per_token: null,
      supports_caching: false,
    },
  ],
  excluded: [{ execution_provider: "Io Net", reason: "LOW_UPTIME" }],
};

/** 비교할 업체가 없는 응답. 상세 패널의 다른 시험에서는 이 값이 기본이다 */
export const NO_RANKING: Schemas["ProviderRankingResponse"] = {
  items: [],
  excluded: [],
};

export const PROVIDERS: Schemas["ProviderListResponse"] = {
  items: [
    { provider: "openai", model_count: 3 },
    { provider: "mistralai", model_count: 1 },
  ],
};

type Reply = { status: number; body: unknown };
type Replies = {
  list?: Reply;
  providers?: Reply;
  detail?: Reply;
  update?: Reply;
  test?: Reply;
  status?: Reply;
  openrouter?: Reply;
  newModels?: Reply;
  discoveries?: Reply;
  ranking?: Reply;
  register?: Reply;
};

const DETAIL_PATH = /\/api\/models\/\d+$/;
const TEST_PATH = /\/api\/models\/\d+\/test$/;
const RANKING_PATH = /\/api\/models\/\d+\/execution-providers\/ranking$/;
const STATUS_PATH = /\/api\/models\/\d+\/status$/;

function replyFor(request: Request, replies: Replies): Reply {
  const url = request.url;
  const { pathname } = new URL(url);
  if (pathname === "/api/models" && request.method === "POST") {
    return replies.register ?? { status: 201, body: DETAIL };
  }
  if (pathname === "/api/models/openrouter/discoveries") {
    return replies.discoveries ?? { status: 200, body: NO_DISCOVERIES };
  }
  if (pathname === "/api/models/openrouter/new") {
    return replies.newModels ?? { status: 200, body: NO_NEW_MODELS };
  }
  if (pathname === "/api/models/openrouter") {
    return replies.openrouter ?? { status: 200, body: OPENROUTER };
  }
  if (RANKING_PATH.test(pathname)) {
    return replies.ranking ?? { status: 200, body: NO_RANKING };
  }
  if (url.endsWith("/api/models/providers")) {
    return replies.providers ?? { status: 200, body: PROVIDERS };
  }
  if (STATUS_PATH.test(new URL(url).pathname)) {
    return replies.status ?? { status: 200, body: DETAIL };
  }
  if (TEST_PATH.test(new URL(url).pathname)) {
    return replies.test ?? { status: 200, body: TEST_RESULT };
  }
  if (DETAIL_PATH.test(new URL(url).pathname)) {
    return request.method === "PATCH"
      ? (replies.update ?? { status: 200, body: DETAIL })
      : (replies.detail ?? { status: 200, body: DETAIL });
  }
  return replies.list ?? { status: 200, body: LIST };
}

/** 브라우저 fetch를 P-03 API 응답으로 대체. 보낸 요청은 반환된 목록에 기록 */
export function stubModelsApi(initial: Replies = {}) {
  const replies: Replies = { ...initial };
  const requests: { url: URL; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    const text = await request.clone().text();
    requests.push({
      url: new URL(request.url),
      method: request.method,
      body: text === "" ? undefined : JSON.parse(text),
    });
    const reply = replyFor(request, replies);
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  return { requests, replies };
}

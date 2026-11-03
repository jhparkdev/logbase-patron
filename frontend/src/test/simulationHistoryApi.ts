import { vi } from "vitest";
import type { components } from "../shared/api/schema";
import { MODEL_ROW } from "./modelsApi";

type Schemas = components["schemas"];

const JSON_HEADERS = { "Content-Type": "application/json" };

export const RUN_ID = "01a1611f-3e80-73c5-a130-3efa5a1f75de";

export const HISTORY_ITEM: Schemas["SimulationHistoryItem"] = {
  simulation_id: RUN_ID,
  rerun_of_simulation_id: null,
  test_type: "SCENARIO",
  scenario_code: "DATA_SUMMARY",
  status: "PARTIAL_SUCCESS",
  model_count: 2,
  requested_at: "2026-10-22T01:00:00Z",
  completed_at: "2026-10-22T01:00:05Z",
  executed_by: 1,
  final_result_count: 2,
  success_count: 1,
  failure_count: 1,
  confirmed_cost_usd: "0.125",
  estimated_cost_usd: null,
  total_cost_usd: "0.125",
  unknown_cost_count: 1,
  cost_check_status: "미확인 포함",
  inactive_model_count: 1,
};

export const HISTORY_LIST: Schemas["SimulationHistoryList"] = {
  items: [HISTORY_ITEM],
  total: 1,
};

const { inactive_model_count: _, ...SUMMARY } = HISTORY_ITEM;

export const RUN_DETAIL: Schemas["SimulationDetailResponse"] = {
  summary: SUMMARY,
  results: [
    {
      slot_no: 1,
      request_id: "01a1611f-3e80-73c5-a130-3efa5a1f7601",
      model_id: 2,
      model_display_name_at_run: "Mistral Nemo",
      model_status_at_run: "ACTIVE",
      execution_provider: "DeepInfra",
      execution_config: { temperature: 0.9, max_tokens: 512 },
      actual_provider: "DeepInfra",
      actual_model: "mistralai/mistral-nemo",
      status: "SUCCESS",
      error_type: null,
      latency_ms: 1500,
      input_tokens: 10,
      output_tokens: 20,
      cost_usd: "0.125",
      cost_status: "CONFIRMED",
      json_parse_status: "PASSED",
      schema_validation_status: "NOT_APPLICABLE",
      missing_required_fields: null,
      comparability_note: null,
      output_type: "TEXT",
      response_text: "모델 응답 원문",
      output_images: [],
      error_message: null,
    },
    {
      slot_no: 2,
      request_id: "01a1611f-3e80-73c5-a130-3efa5a1f7602",
      model_id: 4,
      model_display_name_at_run: "Nova Micro",
      model_status_at_run: "ACTIVE",
      execution_provider: "Amazon",
      execution_config: {},
      actual_provider: null,
      actual_model: null,
      status: "TIMEOUT",
      error_type: "TIMEOUT_ERROR",
      latency_ms: null,
      input_tokens: null,
      output_tokens: null,
      cost_usd: null,
      cost_status: "UNKNOWN",
      json_parse_status: null,
      schema_validation_status: "NOT_EXECUTED",
      missing_required_fields: null,
      comparability_note: null,
      output_type: "TEXT",
      response_text: null,
      output_images: [],
      error_message: "응답 시간을 초과했습니다.",
    },
  ],
};

export const RERUN_DRAFT: Schemas["SimulationRerunDraft"] = {
  rerun_of_simulation_id: RUN_ID,
  test_type: "SCENARIO",
  scenario_id: 3,
  prompt_text: "과거 Prompt 원문",
  input_text: "저장한 입력",
  json_schema: { type: "object" },
  execution_config: { temperature: 0.3, max_tokens: 512 },
  routing_policy: { allow_fallbacks: false },
  models: [
    {
      model_id: 2,
      execution_provider: "DeepInfra",
      execution_config: {},
      current_display_name: "Mistral Nemo",
      current_status: "ACTIVE",
      selectable: true,
    },
    {
      model_id: 4,
      execution_provider: "Amazon",
      execution_config: {},
      current_display_name: "Nova Micro",
      current_status: "INACTIVE",
      selectable: false,
    },
  ],
  asset_ids: [],
  images: [],
  output_type: "TEXT",
  image_config: null,
  rerunnable: true,
  blocked_reason: null,
};

export const SCENARIO: Schemas["ScenarioRead"] = {
  scenario_id: 3,
  scenario_code: "DATA_SUMMARY",
  name: "데이터 요약",
  description: null,
  input_type: "TEXT",
  prompt_template: "다음 데이터를 요약하세요.",
  default_json_schema: null,
  default_execution_config: {},
  is_active: true,
};

export const SCENARIOS: Schemas["ScenarioList"] = { items: [SCENARIO] };

type Reply = { status: number; body: unknown };
type Replies = {
  list?: Reply;
  models?: Reply;
  scenarios?: Reply;
  detail?: Reply;
  draft?: Reply;
};

export const ACTIVE_MODEL: Schemas["ModelRead"] = {
  ...MODEL_ROW,
  model_id: 2,
  display_name: "Mistral Nemo",
  provider: "mistralai",
};

const MODELS: Schemas["ModelListResponse"] = {
  items: [ACTIVE_MODEL],
  page: 1,
  page_size: 100,
  total: 1,
};

export const EXECUTION_PROVIDERS: Schemas["ExecutionProviderListResponse"] = {
  items: [
    { execution_provider: "DeepInfra", status: 0, uptime_last_1d: "99.5" },
    { execution_provider: "DekaLLM", status: 0, uptime_last_1d: null },
  ],
};

function replyFor(pathname: string, replies: Replies): Reply {
  if (pathname === "/api/models")
    return replies.models ?? { status: 200, body: MODELS };
  if (pathname === "/api/scenarios")
    return replies.scenarios ?? { status: 200, body: SCENARIOS };
  if (pathname.endsWith("/execution-providers"))
    return { status: 200, body: EXECUTION_PROVIDERS };
  if (pathname.endsWith("/images/limits"))
    return {
      status: 200,
      body: {
        max_count: 4,
        max_bytes: 5_242_880,
        mime_types: ["image/jpeg", "image/png", "image/webp"],
      },
    };
  if (pathname.endsWith("/rerun-draft"))
    return replies.draft ?? { status: 200, body: RERUN_DRAFT };
  if (pathname === "/api/simulations")
    return replies.list ?? { status: 200, body: HISTORY_LIST };
  return replies.detail ?? { status: 200, body: RUN_DETAIL };
}

/** 브라우저 fetch를 P-05 API 응답으로 대체. 보낸 요청은 반환된 목록에 기록 */
export function stubHistoryApi(initial: Replies = {}) {
  const replies: Replies = { ...initial };
  const requests: URL[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    const url = new URL(request.url);
    requests.push(url);
    const reply = replyFor(url.pathname, replies);
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: JSON_HEADERS,
    });
  });
  return { requests, replies };
}

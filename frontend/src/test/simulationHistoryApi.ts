import { vi } from "vitest";
import type { components } from "../shared/api/schema";

type Schemas = components["schemas"];

const JSON_HEADERS = { "Content-Type": "application/json" };

export const RUN_ID = "01a1611f-3e80-73c5-a130-3efa5a1f75de";

export const HISTORY_ITEM: Schemas["SimulationHistoryItem"] = {
  simulation_id: RUN_ID,
  rerun_of_simulation_id: null,
  test_type: "SCENARIO",
  scenario_code: "PRODUCT_DESCRIPTION",
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
      response_text: "모델 응답 원문",
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
      response_text: null,
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
  rerunnable: true,
  blocked_reason: null,
};

type Reply = { status: number; body: unknown };
type Replies = {
  list?: Reply;
  models?: Reply;
  detail?: Reply;
  draft?: Reply;
};

const MODELS: Pick<
  Schemas["ModelListResponse"],
  "page" | "page_size" | "total"
> & {
  items: Pick<Schemas["ModelRead"], "model_id" | "display_name">[];
} = {
  items: [{ model_id: 2, display_name: "Mistral Nemo" }],
  page: 1,
  page_size: 100,
  total: 1,
};

function replyFor(pathname: string, replies: Replies): Reply {
  if (pathname === "/api/models")
    return replies.models ?? { status: 200, body: MODELS };
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

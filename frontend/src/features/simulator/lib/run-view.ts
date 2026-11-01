import type { components } from "../../../shared/api/schema";
import type { CostView, RunView, SlotView, StatusView } from "./presentation";

type Schemas = components["schemas"];
type Result = Schemas["SimulationModelResult"];

const RUN_STATUS: Record<Schemas["SimulationStatus"], StatusView> = {
  PENDING: { label: "대기", tone: "grey", ongoing: true },
  RUNNING: { label: "진행 중", tone: "grey", ongoing: true },
  SUCCESS: { label: "성공", tone: "green", ongoing: false },
  PARTIAL_SUCCESS: { label: "부분 성공", tone: "yellow", ongoing: false },
  FAILED: { label: "실패", tone: "red", ongoing: false },
  CANCELLED: { label: "취소됨", tone: "grey", ongoing: false },
};
const SLOT_STATUS: Record<Schemas["RequestStatus"], StatusView> = {
  PENDING: { label: "대기", tone: "grey", ongoing: true },
  RUNNING: { label: "진행 중", tone: "grey", ongoing: true },
  SUCCESS: { label: "성공", tone: "green", ongoing: false },
  FAILED: { label: "실패", tone: "red", ongoing: false },
  TIMEOUT: { label: "시간 초과", tone: "yellow", ongoing: false },
  CANCELLED: { label: "취소됨", tone: "grey", ongoing: false },
};
const VALIDATION: Record<Schemas["ValidationStatus"], string> = {
  PASSED: "성공",
  FAILED: "실패",
  NOT_APPLICABLE: "미적용",
  NOT_EXECUTED: "미실행",
};
const VALIDATION_NOT_RUN = VALIDATION.NOT_EXECUTED;

function toCost(result: Result): CostView {
  if (result.cost_status === "UNKNOWN" || result.cost_usd === null)
    return { kind: "unknown", amount: null };
  return {
    kind: result.cost_status === "ESTIMATED" ? "estimated" : "confirmed",
    amount: result.cost_usd,
  };
}

function toSlot(result: Result): SlotView {
  return {
    key: result.request_id,
    name: result.model_display_name_at_run,
    provider: result.execution_provider,
    actualModel: result.actual_model,
    actualProvider: result.actual_provider,
    status: SLOT_STATUS[result.status],
    durationMs: result.latency_ms,
    inputTokens: result.input_tokens,
    outputTokens: result.output_tokens,
    cost: toCost(result),
    jsonValidation: result.json_parse_status
      ? VALIDATION[result.json_parse_status]
      : VALIDATION_NOT_RUN,
    schemaValidation: result.schema_validation_status
      ? VALIDATION[result.schema_validation_status]
      : VALIDATION_NOT_RUN,
    missingFields: result.missing_required_fields ?? undefined,
    response: result.response_text,
    errorMessage: result.error_message ?? undefined,
    comparisonNote: result.comparability_note,
  };
}

/** 합산은 서버의 일이다. 서버가 합계를 주지 않으므로 금액이 하나일 때만 합계로 쓴다. */
function serverTotal(
  confirmed: string | null,
  estimated: string | null,
): string | null {
  return confirmed !== null && estimated !== null
    ? null
    : (confirmed ?? estimated);
}

export function toRunView(
  detail: Schemas["SimulationDetailResponse"],
): RunView {
  const { summary } = detail;
  return {
    key: summary.simulation_id,
    status: RUN_STATUS[summary.status],
    requestedAt: summary.requested_at,
    durationMs: summary.completed_at
      ? Date.parse(summary.completed_at) - Date.parse(summary.requested_at)
      : null,
    modelCount: summary.model_count,
    successCount: summary.success_count,
    failureCount: summary.failure_count,
    confirmedCost: summary.confirmed_cost_usd,
    estimatedCost: summary.estimated_cost_usd,
    totalCost: serverTotal(
      summary.confirmed_cost_usd,
      summary.estimated_cost_usd,
    ),
    unknownCostCount: summary.unknown_cost_count,
    slots: detail.results.map(toSlot),
  };
}

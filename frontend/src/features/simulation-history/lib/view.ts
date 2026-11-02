import { ApiError } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import type {
  HistoryDetailState,
  HistoryDetailView,
  HistoryOption,
  HistoryRow,
} from "./presentation";
import { STATUS_LABELS } from "./search";

type Schemas = components["schemas"];
type RunStatus = Schemas["SimulationStatus"];
type RunDetail = Schemas["SimulationDetailResponse"];
type RerunDraft = Schemas["SimulationRerunDraft"];

const STATUS_TONES: Record<RunStatus, HistoryRow["status"]["tone"]> = {
  PENDING: "grey",
  RUNNING: "grey",
  SUCCESS: "green",
  PARTIAL_SUCCESS: "yellow",
  FAILED: "red",
  CANCELLED: "grey",
};
const CUSTOM_LABEL = "Custom Prompt";
const SCENARIO_LABEL = "기본 시나리오";
const NOT_SPECIFIED = "미지정";
const NO_SCENARIO_NAMES: ReadonlyMap<string, string> = new Map();
const JSON_INDENT = 2;

export function isRunOngoing(status: RunStatus): boolean {
  return status === "PENDING" || status === "RUNNING";
}

/** 이력 응답에는 시나리오 코드만 있다. 코드는 내부 값이라 화면에는 이름으로 바꿔 보여 준다. */
export function scenarioNames(
  scenarios: readonly Pick<Schemas["ScenarioRead"], "scenario_code" | "name">[],
): ReadonlyMap<string, string> {
  return new Map(scenarios.map((item) => [item.scenario_code, item.name]));
}

export function toHistoryRow(
  item: Schemas["SimulationHistoryItem"],
  names: ReadonlyMap<string, string> = NO_SCENARIO_NAMES,
): HistoryRow {
  return {
    key: item.simulation_id,
    requestedAt: item.requested_at,
    scenario:
      item.test_type === "CUSTOM"
        ? CUSTOM_LABEL
        : (names.get(item.scenario_code ?? "") ?? SCENARIO_LABEL),
    modelCount: item.model_count,
    status: {
      label: STATUS_LABELS[item.status],
      tone: STATUS_TONES[item.status],
    },
    cost: {
      confirmed: item.confirmed_cost_usd,
      estimated: item.estimated_cost_usd,
      unknownCount: item.unknown_cost_count,
      checkStatus: item.cost_check_status,
    },
    inactiveModelCount: item.inactive_model_count,
  };
}

export function toModelOptions(
  models: readonly Pick<Schemas["ModelRead"], "model_id" | "display_name">[],
): HistoryOption[] {
  return models.map((model) => ({
    key: String(model.model_id),
    name: model.display_name,
  }));
}

export function toScenarioOptions(
  scenarios: readonly Pick<Schemas["ScenarioRead"], "scenario_id" | "name">[],
): HistoryOption[] {
  return scenarios.map((scenario) => ({
    key: String(scenario.scenario_id),
    name: scenario.name,
  }));
}

// 실행 공통 설정이다. 모델별로 실제 적용한 값은 결과 카드의 "적용 설정"에서 따로 보여 준다.
function configValue(config: RerunDraft["execution_config"], name: string) {
  const value = config[name];
  return value === undefined || value === null ? NOT_SPECIFIED : String(value);
}

function toInput(draft: RerunDraft): HistoryDetailView["input"] {
  if (!draft.rerunnable && !draft.asset_ids.length) return { kind: "missing" };
  return {
    kind: "available",
    prompt: draft.prompt_text,
    text: draft.input_text ?? "",
    schema: draft.json_schema
      ? JSON.stringify(draft.json_schema, null, JSON_INDENT)
      : "",
    // 이미지 조회 API가 없어 원래 파일 이름을 알 수 없다. 재실행 불가 사유는 입력 누락 하나뿐이다.
    attachments: draft.asset_ids.map((assetId, index) => ({
      key: assetId,
      name: `이미지 ${index + 1}`,
      available: draft.rerunnable,
    })),
  };
}

export function toHistoryDetail(
  run: RunDetail,
  draft: RerunDraft,
): HistoryDetailView {
  const source = run.summary.rerun_of_simulation_id;
  return {
    key: run.summary.simulation_id,
    input: toInput(draft),
    settings: [
      {
        label: "테스트 유형",
        value: draft.test_type === "SCENARIO" ? SCENARIO_LABEL : CUSTOM_LABEL,
      },
      {
        label: "공통 Temperature",
        value: configValue(draft.execution_config, "temperature"),
      },
      {
        label: "공통 최대 출력 토큰",
        value: configValue(draft.execution_config, "max_tokens"),
      },
      {
        label: "공통 추론 강도",
        value: configValue(draft.execution_config, "reasoning_effort"),
      },
      {
        label: "Provider·Fallback 정책",
        value: JSON.stringify(draft.routing_policy, null, JSON_INDENT),
      },
      ...(source ? [{ label: "재실행 원본 ID", value: source }] : []),
    ],
    // 같은 모델·Provider를 설정만 달리해 비교할 수 있어 칸 순서까지 키에 넣는다
    models: draft.models.map((model, index) => ({
      key: `${index}:${model.model_id}:${model.execution_provider}`,
      name: model.current_display_name,
      provider: model.execution_provider,
      currentState: model.selectable ? "active" : "inactive",
    })),
  };
}

type Loaded<T> = { data: T | undefined; error: unknown };

/** 받은 값이 있으면 폴링이 잠깐 실패해도 유지한다. 없는 실행(404)은 조회 실패와 구분한다. */
export function historyDetailState(
  run: Loaded<RunDetail>,
  draft: Loaded<RerunDraft>,
): HistoryDetailState {
  if (run.data && draft.data)
    return { kind: "ready", value: toHistoryDetail(run.data, draft.data) };
  const errors = [run, draft].flatMap((query) =>
    query.data ? [] : query.error ? [query.error] : [],
  );
  if (!errors.length) return { kind: "loading" };
  return errors.some(
    (error) => error instanceof ApiError && error.status === 404,
  )
    ? { kind: "missing" }
    : { kind: "error" };
}

import type { components } from "../../../shared/api/schema";
import { choiceKey } from "./catalog";
import { createComparison } from "./comparisons";
import { createDefaultValues, type SimulatorFormValues } from "./form";
import type { ModelChoice, ScenarioChoice } from "./presentation";

type RerunDraft = components["schemas"]["SimulationRerunDraft"];
type Config = RerunDraft["execution_config"];

// 초안과 현재 모델 목록을 모두 확인한 뒤 ready 값을 전달한다.
export type SimulatorRestoreView =
  | { kind: "unavailable" | "loading" | "error" | "missing" | "scenario" }
  | {
      kind: "ready";
      key: string;
      values: SimulatorFormValues;
      choices: ModelChoice[];
      scenarios: ScenarioChoice[];
    };

const JSON_INDENT = 2;
const CONFIG_KEYS = ["temperature", "max_tokens", "reasoning_effort"] as const;

function configText(config: Config, key: (typeof CONFIG_KEYS)[number]) {
  const value = config[key];
  return value === undefined || value === null ? "" : String(value);
}

function sameConfig(a: Config, b: Config) {
  return CONFIG_KEYS.every((key) => configText(a, key) === configText(b, key));
}

/** 과거 실행을 폼 값으로 되돌린다. 공통 설정과 같은 칸은 공통을 따르게 둔다. */
export function toRerunValues(draft: RerunDraft): SimulatorFormValues {
  return createDefaultValues({
    mode: "custom",
    prompt: draft.prompt_text,
    text: draft.input_text ?? "",
    jsonSchema: draft.json_schema
      ? JSON.stringify(draft.json_schema, null, JSON_INDENT)
      : "",
    temperature: configText(draft.execution_config, "temperature"),
    maxTokens: configText(draft.execution_config, "max_tokens"),
    reasoningEffort: configText(draft.execution_config, "reasoning_effort"),
    existingAssetIds: draft.asset_ids,
    comparisons: draft.models.map((model) => {
      const comparison = createComparison(
        choiceKey(model.model_id, model.execution_provider),
      );
      if (sameConfig(model.execution_config, draft.execution_config))
        return comparison;
      return {
        ...comparison,
        settings: {
          mode: "custom" as const,
          temperature: configText(model.execution_config, "temperature"),
          maxTokens: configText(model.execution_config, "max_tokens"),
          reasoningEffort: configText(
            model.execution_config,
            "reasoning_effort",
          ),
        },
      };
    }),
  });
}

export function rerunRestoreView(
  state: {
    draft: RerunDraft | undefined;
    catalogReady: boolean;
    error: "missing" | "error" | null;
  },
  key: string,
  choices: ModelChoice[],
): SimulatorRestoreView {
  if (state.error) return { kind: state.error };
  if (!state.draft) return { kind: "loading" };
  // 시나리오 목록 API가 없다. 직접 작성으로 바꾸면 실행 유형이 달라져 비교 조건이 어긋난다.
  if (state.draft.test_type === "SCENARIO") return { kind: "scenario" };
  if (!state.draft.rerunnable) return { kind: "missing" };
  if (!state.catalogReady) return { kind: "loading" };
  return {
    kind: "ready",
    key,
    values: toRerunValues(state.draft),
    choices,
    scenarios: [],
  };
}

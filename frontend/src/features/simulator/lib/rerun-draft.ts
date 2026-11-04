import type { components } from "../../../shared/api/schema";
import { choiceKey } from "./catalog";
import { type ComparisonValues, createComparison } from "./comparisons";
import { createDefaultValues, type SimulatorFormValues } from "./form";
import type { ModelChoice, ScenarioChoice } from "./presentation";
import { restorableScenarios } from "./scenarios";

type RerunDraft = components["schemas"]["SimulationRerunDraft"];
type Config = RerunDraft["execution_config"];
type Scenario = components["schemas"]["ScenarioRead"];

// 초안과 현재 모델·시나리오 목록을 모두 확인한 뒤 ready 값을 전달한다.
export type SimulatorRestoreView =
  | { kind: "unavailable" | "loading" | "error" | "missing" }
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

function hasConfig(config: Config) {
  return CONFIG_KEYS.some((key) => configText(config, key) !== "");
}

function customSettings(config: Config): ComparisonValues["settings"] {
  return {
    mode: "custom",
    temperature: configText(config, "temperature"),
    maxTokens: configText(config, "max_tokens"),
    reasoningEffort: configText(config, "reasoning_effort"),
  };
}

/**
 * 과거 실행을 폼 값으로 되돌린다.
 * 텍스트 실행은 공통 설정을 끄고, 칸마다 서버가 실제로 적용한 값을 모델별 설정으로 채운다.
 * 공통값·시나리오 기본값을 다시 물려주면 그사이 기본값이나 모델 지원 정보가 바뀌었을 때 과거와 다른 요청이 되기 때문이다.
 * 이미지 생성 실행은 기존처럼 공통 설정과 같은 칸은 공통을 따르게 둔다.
 */
export function toRerunValues(draft: RerunDraft): SimulatorFormValues {
  const perSlot = draft.output_type === "TEXT";
  return createDefaultValues({
    mode: draft.test_type === "SCENARIO" ? "scenario" : "custom",
    scenarioKey: draft.scenario_id === null ? "" : String(draft.scenario_id),
    prompt: draft.prompt_text,
    text: draft.input_text ?? "",
    jsonSchema: draft.json_schema
      ? JSON.stringify(draft.json_schema, null, JSON_INDENT)
      : "",
    commonEnabled: !perSlot,
    temperature: configText(draft.execution_config, "temperature"),
    maxTokens: configText(draft.execution_config, "max_tokens"),
    reasoningEffort: configText(draft.execution_config, "reasoning_effort"),
    existingAssetIds: draft.asset_ids,
    existingImageNames: Object.fromEntries(
      draft.images.flatMap((image) =>
        image.original_filename === null
          ? []
          : [[image.asset_id, image.original_filename]],
      ),
    ),
    outputType: draft.output_type,
    imageCount:
      draft.image_config?.n == null ? "" : String(draft.image_config.n),
    imageQuality: draft.image_config?.quality ?? "",
    comparisons: draft.models.map((model) => {
      const comparison = createComparison(
        choiceKey(model.model_id, model.execution_provider),
      );
      const custom = perSlot
        ? hasConfig(model.execution_config)
        : !sameConfig(model.execution_config, draft.execution_config);
      return custom
        ? { ...comparison, settings: customSettings(model.execution_config) }
        : comparison;
    }),
  });
}

export function rerunRestoreView(
  state: {
    draft: RerunDraft | undefined;
    catalogReady: boolean;
    error: "missing" | "error" | null;
    scenarios: readonly Scenario[] | undefined;
    scenariosFailed: boolean;
  },
  key: string,
  choices: ModelChoice[],
): SimulatorRestoreView {
  if (state.error) return { kind: state.error };
  if (!state.draft) return { kind: "loading" };
  if (!state.draft.rerunnable) return { kind: "missing" };
  // 직접 작성으로 바꾸면 실행 유형이 달라져 비교 조건이 어긋나므로, 시나리오 실행은 목록 없이 복원하지 않는다.
  if (state.scenariosFailed && state.draft.test_type === "SCENARIO")
    return { kind: "error" };
  if (!state.catalogReady || (!state.scenarios && !state.scenariosFailed))
    return { kind: "loading" };
  return {
    kind: "ready",
    key,
    values: toRerunValues(state.draft),
    choices,
    scenarios: restorableScenarios(
      state.scenarios ?? [],
      state.draft.scenario_id,
    ),
  };
}

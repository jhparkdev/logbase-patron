import type { components } from "../../../shared/api/schema";
import { parseChoiceKey } from "./catalog";
import type { SimulatorDraft } from "./form";

type Schemas = components["schemas"];
type ExecutionConfig = Schemas["ExecutionConfig"];
type Effort = Schemas["ReasoningEffort"];

const EFFORTS = [
  "none",
  "minimal",
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
] as const satisfies readonly Effort[];

function toExecutionConfig(settings: {
  temperature?: number;
  maxTokens?: number;
  reasoningEffort?: string;
}): ExecutionConfig {
  const effort = EFFORTS.find((value) => value === settings.reasoningEffort);
  return {
    ...(settings.temperature !== undefined
      ? { temperature: settings.temperature }
      : {}),
    ...(settings.maxTokens !== undefined
      ? { max_tokens: settings.maxTokens }
      : {}),
    ...(effort ? { reasoning_effort: effort } : {}),
  };
}

/** 폼 값을 실행 요청으로 바꾼다. 업체를 알 수 없는 칸이 있으면 비용이 나가기 전에 멈춘다. */
export function toCreateRequest(
  draft: SimulatorDraft,
  uploadedAssetIds: readonly string[],
  rerunOf?: string,
): Schemas["SimulationCreateRequest"] {
  const scenario = draft.mode === "scenario";
  return {
    test_type: scenario ? "SCENARIO" : "CUSTOM",
    ...(scenario ? { scenario_id: Number(draft.scenarioKey) } : {}),
    ...(rerunOf ? { rerun_of_simulation_id: rerunOf } : {}),
    prompt_text: draft.prompt,
    input_text: draft.text || null,
    json_schema: draft.jsonSchema.trim() ? JSON.parse(draft.jsonSchema) : null,
    // null은 공통 끔이다. 서버는 시나리오 기본값과 공통값을 쓰지 않고 칸에 넣은 값만 보낸다.
    execution_config: draft.commonEnabled ? toExecutionConfig(draft) : null,
    models: draft.comparisons.map((comparison) => {
      const selected = parseChoiceKey(comparison.modelKey);
      if (!selected) throw new Error("서버 업체를 확인할 수 없는 모델이에요.");
      return {
        ...selected,
        execution_config: toExecutionConfig(comparison.settings),
      };
    }),
    asset_ids: [...draft.existingAssetIds, ...uploadedAssetIds],
    output_type: "TEXT",
  };
}

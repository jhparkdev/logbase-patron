import { requestedSettings } from "./comparisons";
import type { SimulatorDraft } from "./form";
import {
  PARAMETER_LABELS,
  PARAMETER_NAMES,
  parameterIssue,
  type TuningParameter,
} from "./parameters";

// 화면 전용 props다. HTTP 계약과 요청·응답 타입은 OpenAPI 준비 후 별도 adapter에서 연결한다.
export type ModelChoice = {
  key: string;
  name: string;
  provider: string;
  // models.provider(제작사)를 adapter가 별도로 전달한다. 위 provider는 실행 업체다.
  creator?: string;
  selectable: boolean;
  unavailableReason?: string;
  supportsImages: boolean;
  supportedParameters: readonly string[];
  tuningParameters?: readonly TuningParameter[];
};
export type ScenarioChoice = {
  key: string;
  name: string;
  prompt: string;
  imageRequired: boolean;
  schemaText: string;
  defaults: {
    temperature?: number;
    maxTokens?: number;
    reasoningEffort?: string;
  };
};
export type StatusView = {
  label: string;
  tone: "green" | "red" | "yellow" | "grey";
  ongoing?: boolean;
};
export type CostView =
  | { kind: "confirmed" | "estimated"; amount: string }
  | { kind: "unknown"; amount: null };
export type SlotView = {
  key: string;
  name: string;
  provider: string;
  actualModel?: string | null;
  actualProvider?: string | null;
  status: StatusView;
  durationMs: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  cost: CostView;
  jsonValidation: string;
  schemaValidation: string;
  missingFields?: string[];
  response: string | null;
  errorMessage?: string;
  comparisonNote?: string | null;
  // 실행 당시의 모델 상태. 현재 상태와 다를 수 있다.
  statusAtRun?: string;
  // 이 칸에 실제로 적용한 설정. 빈 배열은 모델 기본값으로 호출했다는 뜻이다.
  settings?: readonly { label: string; value: string }[];
};
export type RunView = {
  key: string;
  status: StatusView;
  requestedAt: string;
  durationMs: number | null;
  modelCount: number;
  successCount: number;
  failureCount: number;
  confirmedCost: string | null;
  estimatedCost: string | null;
  totalCost: string | null;
  unknownCostCount: number;
  slots: SlotView[];
};
export type ResultsView =
  | { kind: "empty" | "loading" | "error" }
  | { kind: "ready"; run: RunView; refreshing?: boolean };
export const SORT_KEYS = [
  "model",
  "duration",
  "inputTokens",
  "outputTokens",
  "cost",
] as const;
export type ResultSort = {
  key: (typeof SORT_KEYS)[number];
  direction: "asc" | "desc";
};

export function selectionIssues(
  draft: SimulatorDraft,
  choices: ModelChoice[],
  scenarios: ScenarioChoice[],
): string[] {
  const issues: string[] = [];
  const hasImages = draft.files.length + draft.existingAssetIds.length > 0;
  const scenario =
    draft.mode === "scenario"
      ? scenarios.find((item) => item.key === draft.scenarioKey)
      : undefined;
  if (draft.mode === "scenario" && !scenario)
    issues.push("시나리오를 다시 선택하시기 바랍니다.");
  if (draft.mode === "scenario" && scenario?.imageRequired && !hasImages)
    issues.push("선택한 시나리오에 사용할 이미지를 추가하시기 바랍니다.");
  const seen = new Set<string>();
  for (const comparison of draft.comparisons) {
    const choice = choices.find((item) => item.key === comparison.modelKey);
    if (!choice?.selectable) {
      issues.push(
        "선택할 수 없는 모델이 있습니다. 모델을 다시 선택하시기 바랍니다.",
      );
      continue;
    }
    if (hasImages && !choice.supportsImages)
      issues.push(`${choice.name}은 이미지 입력을 지원하지 않습니다.`);
    const settings = requestedSettings(comparison, draft, scenario?.defaults);
    for (const key of [
      "temperature",
      "maxTokens",
      "reasoningEffort",
    ] as const) {
      const value = settings[key];
      if (value === undefined) continue;
      const parameter = choice.tuningParameters?.find(
        (item) => item.key === key,
      );
      if (
        !parameter &&
        !choice.supportedParameters.includes(PARAMETER_NAMES[key])
      )
        issues.push(
          `${choice.name}은 ${PARAMETER_LABELS[key]} 지정을 지원하지 않습니다.`,
        );
      if (
        comparison.settings.mode === "custom" &&
        comparison.settings[key] !== undefined &&
        !parameter
      )
        issues.push(
          `${choice.name}의 모델별 설정 지원 정보를 확인할 수 없습니다.`,
        );
      if (
        key === "reasoningEffort" &&
        !parameter &&
        choice.supportedParameters.includes(PARAMETER_NAMES[key])
      )
        issues.push(
          `${choice.name}의 추론 강도 지원 선택지를 확인할 수 없습니다. 모델을 다시 선택하거나 추론 강도 설정을 해제하시기 바랍니다.`,
        );
      if (parameter) {
        const issue = parameterIssue(parameter, value);
        if (issue) issues.push(`${choice.name}: ${issue}`);
      }
    }
    const fingerprint = JSON.stringify([comparison.modelKey, settings]);
    if (seen.has(fingerprint))
      issues.push(
        "동일한 요청 설정을 가진 비교 항목이 있습니다. 설정을 변경하거나 항목을 제거하시기 바랍니다.",
      );
    seen.add(fingerprint);
    if (
      draft.jsonSchema.trim() &&
      !choice.supportedParameters.some(
        (value) =>
          value === "response_format" || value === "structured_outputs",
      )
    )
      issues.push(`${choice.name}은 구조화 출력 설정을 지원하지 않습니다.`);
  }
  return [...new Set(issues)];
}

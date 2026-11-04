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
  // 토큰당 단가(USD 문자열). 모르면 null이고 0으로 보여 주지 않는다.
  price?: { input: string | null; output: string | null };
};

const STRUCTURED_OUTPUT_PARAMETERS = ["response_format", "structured_outputs"];

export function supportsStructuredOutput(choice: ModelChoice): boolean {
  return choice.supportedParameters.some((value) =>
    STRUCTURED_OUTPUT_PARAMETERS.includes(value),
  );
}
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
    issues.push("시나리오를 다시 골라 주세요.");
  if (draft.mode === "scenario" && scenario?.imageRequired && !hasImages)
    issues.push("선택한 시나리오에 쓸 이미지를 추가해 주세요.");
  const seen = new Set<string>();
  for (const comparison of draft.comparisons) {
    const choice = choices.find((item) => item.key === comparison.modelKey);
    if (!choice?.selectable) {
      issues.push("고를 수 없는 모델이 있어요. 모델을 다시 골라 주세요.");
      continue;
    }
    if (hasImages && !choice.supportsImages)
      issues.push(`${choice.name}은 이미지 입력을 지원하지 않아요.`);
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
          `${choice.name}은 ${PARAMETER_LABELS[key]} 지정을 지원하지 않아요.`,
        );
      if (
        comparison.settings.mode === "custom" &&
        comparison.settings[key] !== undefined &&
        !parameter
      )
        issues.push(
          `${choice.name}의 모델별 설정 지원 정보를 확인할 수 없어요.`,
        );
      if (
        key === "reasoningEffort" &&
        !parameter &&
        choice.supportedParameters.includes(PARAMETER_NAMES[key])
      )
        issues.push(
          `${choice.name}의 추론 강도 지원 선택지를 확인할 수 없어요. 모델을 다시 고르거나 추론 강도 설정을 해제해 주세요.`,
        );
      if (parameter) {
        const issue = parameterIssue(parameter, value);
        if (issue) issues.push(`${choice.name}: ${issue}`);
      }
    }
    const fingerprint = JSON.stringify([comparison.modelKey, settings]);
    if (seen.has(fingerprint))
      issues.push(
        "요청 설정이 같은 비교 항목이 있어요. 설정을 바꾸거나 항목을 제거해 주세요.",
      );
    seen.add(fingerprint);
    if (draft.jsonSchema.trim() && !supportsStructuredOutput(choice))
      issues.push(`${choice.name}은 구조화 출력 설정을 지원하지 않아요.`);
  }
  return [...new Set(issues)];
}

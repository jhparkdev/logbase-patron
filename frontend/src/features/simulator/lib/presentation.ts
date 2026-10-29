import type { SimulatorDraft } from "./form";

// 화면 전용 props다. HTTP 계약과 요청·응답 타입은 OpenAPI 준비 후 별도 adapter에서 연결한다.
export type ModelChoice = {
  key: string;
  name: string;
  provider: string;
  selectable: boolean;
  unavailableReason?: string;
  supportsImages: boolean;
  supportedParameters: readonly string[];
};
export type ScenarioChoice = {
  key: string;
  name: string;
  prompt: string;
  imageRequired: boolean;
  schemaText: string;
  defaults: { temperature?: number; maxTokens?: number };
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
  const scenario = scenarios.find((item) => item.key === draft.scenarioKey);
  if (draft.mode === "scenario" && !scenario)
    issues.push("시나리오를 다시 선택해 주세요.");
  if (
    draft.mode === "scenario" &&
    scenario?.imageRequired &&
    !draft.files.length
  )
    issues.push("선택한 시나리오에 사용할 이미지를 추가해 주세요.");
  for (const key of draft.selections) {
    const choice = choices.find((item) => item.key === key);
    if (!choice?.selectable) {
      issues.push("선택할 수 없는 모델이 있어요. 모델을 다시 선택해 주세요.");
      continue;
    }
    if (draft.files.length && !choice.supportsImages)
      issues.push(`${choice.name}은 이미지 입력을 지원하지 않아요.`);
    if (
      draft.temperature !== undefined &&
      !choice.supportedParameters.includes("temperature")
    )
      issues.push(`${choice.name}은 Temperature 지정을 지원하지 않아요.`);
    if (
      draft.maxTokens !== undefined &&
      !choice.supportedParameters.includes("max_tokens")
    )
      issues.push(`${choice.name}은 최대 출력 토큰 지정을 지원하지 않아요.`);
    if (
      draft.jsonSchema.trim() &&
      !choice.supportedParameters.some(
        (value) =>
          value === "response_format" || value === "structured_outputs",
      )
    )
      issues.push(`${choice.name}은 구조화 출력 설정을 지원하지 않아요.`);
  }
  return [...new Set(issues)];
}

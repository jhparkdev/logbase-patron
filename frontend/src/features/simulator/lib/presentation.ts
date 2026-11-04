import {
  type ComparisonDraft,
  commonSettings,
  type RequestedSettings,
  requestedSettings,
} from "./comparisons";
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

const SETTING_KEYS = ["temperature", "maxTokens", "reasoningEffort"] as const;
type SettingKey = (typeof SETTING_KEYS)[number];

function isDirect(comparison: ComparisonDraft, key: SettingKey) {
  return (
    comparison.settings.mode === "custom" &&
    comparison.settings[key] !== undefined
  );
}

// 공통값·시나리오 기본값에서 물려받은 값을 이 칸의 모델이 받는가. 받지 못하면 서버가 이 칸에서만 뺀다.
function acceptsInherited(
  choice: ModelChoice,
  key: SettingKey,
  value: number | string,
) {
  const parameter = choice.tuningParameters?.find((item) => item.key === key);
  // 선택지를 화면이 모르면 서버 판단에 맡긴다(받으면 보내고, 아니면 뺀다).
  if (!parameter)
    return choice.supportedParameters.includes(PARAMETER_NAMES[key]);
  // 추론 강도는 허용 목록에 없는 값도 서버가 뺀다. 숫자 항목은 범위를 벗어나도 그대로 보내므로 남겨 두고 검사에서 막는다.
  return parameter.kind === "number" || !parameterIssue(parameter, value);
}

/** 칸에 서버가 실제로 보낼 설정. 확인창과 실행 전 검사가 같은 값을 보도록 한 곳에서 계산한다. */
export function appliedSettings(
  comparison: ComparisonDraft,
  draft: SimulatorDraft,
  choice: ModelChoice,
  scenario?: ScenarioChoice,
): RequestedSettings {
  const settings = requestedSettings(
    comparison,
    commonSettings(draft),
    scenario?.defaults,
  );
  return Object.fromEntries(
    SETTING_KEYS.flatMap((key) => {
      const value = settings[key];
      if (value === undefined) return [];
      return isDirect(comparison, key) || acceptsInherited(choice, key, value)
        ? [[key, value]]
        : [];
    }),
  );
}

const HANGUL_SYLLABLE_START = 0xac00;
const HANGUL_SYLLABLE_COUNT = 11172;
const FINAL_CONSONANT_KINDS = 28;

// 마지막 글자에 받침이 있으면 "을", 없으면 "를". 영문 항목명(Temperature)은 받침 없는 발음이라 "를"이다.
function objectParticle(word: string) {
  const offset = word.charCodeAt(word.length - 1) - HANGUL_SYLLABLE_START;
  const hasFinal =
    offset >= 0 &&
    offset < HANGUL_SYLLABLE_COUNT &&
    offset % FINAL_CONSONANT_KINDS !== 0;
  return hasFinal ? "을" : "를";
}

/** 공통 설정에서 물려받았지만 이 모델이 받지 않아 빠지는 항목 안내. 빠지는 항목이 없으면 undefined. */
export function droppedSettingsNote(
  comparison: ComparisonDraft,
  draft: SimulatorDraft,
  choice: ModelChoice,
  scenario?: ScenarioChoice,
) {
  const requested = requestedSettings(
    comparison,
    commonSettings(draft),
    scenario?.defaults,
  );
  const applied = appliedSettings(comparison, draft, choice, scenario);
  const labels = SETTING_KEYS.filter(
    (key) => requested[key] !== undefined && applied[key] === undefined,
  ).map((key) => PARAMETER_LABELS[key]);
  if (!labels.length) return undefined;
  const names = labels.join(", ");
  return `이 모델은 ${names}${objectParticle(names)} 받지 않아 공통 설정 값 대신 모델 기본값으로 실행해요.`;
}

/** 비교 항목 머리글 오른쪽에 쓰는 설정 상태 이름. */
export function comparisonModeLabel(
  mode: "shared" | "custom",
  commonEnabled: boolean,
) {
  if (mode === "custom") return "개별 지정";
  return commonEnabled ? "공통 설정" : "기본값";
}

/** 공통 설정 체크박스 아래 안내. 잠김을 먼저 알린다. */
export function commonSettingsNote(enabled: boolean, locked: boolean) {
  if (locked && !enabled)
    return "모델별 설정을 쓰는 비교 항목이 있어 켤 수 없어요. 모든 항목에서 모델별 설정을 해제하면 켤 수 있어요.";
  if (!enabled)
    return "꺼 두면 공통값과 시나리오 기본값을 쓰지 않아요. 각 모델은 모델별 설정에 넣은 값만 쓰고, 나머지는 기본값으로 실행해요.";
  return "비워 둔 항목은 시나리오를 골랐다면 그 기본값을, 없으면 모델 기본값을 써요. 받지 못하는 모델에서는 그 항목만 빼고 실행해요.";
}

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
    const settings = appliedSettings(comparison, draft, choice, scenario);
    for (const key of SETTING_KEYS) {
      const value = settings[key];
      if (value === undefined) continue;
      const parameter = choice.tuningParameters?.find(
        (item) => item.key === key,
      );
      // 모델별 설정에 직접 넣은 값은 서버가 거절하므로 실행 전에 막는다.
      if (isDirect(comparison, key)) {
        if (
          !parameter &&
          !choice.supportedParameters.includes(PARAMETER_NAMES[key])
        )
          issues.push(
            `${choice.name}은 ${PARAMETER_LABELS[key]} 지정을 지원하지 않아요.`,
          );
        if (!parameter)
          issues.push(
            `${choice.name}의 모델별 설정 지원 정보를 확인할 수 없어요.`,
          );
      }
      if (parameter) {
        const issue = parameterIssue(parameter, value);
        if (issue) issues.push(`${choice.name}: ${issue}`);
      }
    }
    // 서버가 실제로 보내는 값끼리 비교한다.
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

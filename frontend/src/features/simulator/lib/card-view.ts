import { formatCount } from "../../../shared/lib/format";
import { formatPricePerMillion } from "../../../shared/lib/price";
import type { ComparisonValues } from "./comparisons";
import { MODEL_LIMITS } from "./limits";
import { PARAMETER_LABELS, type ParameterKey } from "./parameters";
import {
  type ModelChoice,
  type ScenarioChoice,
  supportsStructuredOutput,
} from "./presentation";

const PARAMETER_KEYS: readonly ParameterKey[] = [
  "temperature",
  "maxTokens",
  "reasoningEffort",
];

/** 모델 카드와 확인창에 적는 100만 토큰당 단가. 입력·출력 중 하나라도 모르면 미확인이다. */
export function unitPriceLabel(price: ModelChoice["price"]): string | null {
  if (!price || price.input === null || price.output === null) return null;
  return `입력 ${formatPricePerMillion(price.input)} · 출력 ${formatPricePerMillion(price.output)}`;
}

export type ResolvedSetting = {
  key: ParameterKey;
  label: string;
  value: string;
  source: "custom" | "common" | "scenario" | "default" | "unsupported";
};

type CommonValues = Record<ParameterKey, string>;

function displayValue(
  key: ParameterKey,
  value: string | number,
  choice?: ModelChoice,
) {
  const parameter = choice?.tuningParameters?.find((item) => item.key === key);
  if (parameter?.kind === "choice")
    return (
      parameter.options.find((option) => option.value === String(value))
        ?.label ?? String(value)
    );
  if (key === "maxTokens" && Number.isFinite(Number(value)))
    return formatCount(Number(value));
  return String(value);
}

/**
 * 카드에 적는 "실제 전송될 설정". requestedSettings와 같은 우선순위(개별 → 공통 → 시나리오)를
 * 입력 중인 문자열 값 그대로 따르고, 어디서 온 값인지 함께 돌려준다.
 */
export function resolvedSettings(
  comparison: ComparisonValues,
  common: CommonValues,
  scenario: ScenarioChoice["defaults"] | undefined,
  choice: ModelChoice | undefined,
): ResolvedSetting[] {
  return PARAMETER_KEYS.map((key) => {
    const label = PARAMETER_LABELS[key];
    const supported =
      !choice?.tuningParameters ||
      choice.tuningParameters.some((item) => item.key === key);
    if (!supported)
      return { key, label, value: "미지원", source: "unsupported" };
    const own =
      comparison.settings.mode === "custom"
        ? comparison.settings[key].trim()
        : "";
    if (own)
      return {
        key,
        label,
        value: displayValue(key, own, choice),
        source: "custom",
      };
    const shared = common[key].trim();
    if (shared)
      return {
        key,
        label,
        value: displayValue(key, shared, choice),
        source: "common",
      };
    const fallback = scenario?.[key];
    if (fallback !== undefined)
      return {
        key,
        label,
        value: displayValue(key, fallback, choice),
        source: "scenario",
      };
    return { key, label, value: "기본값", source: "default" };
  });
}

/** 실행을 누르기 전에 카드에서 바로 보여 줄 충돌. 차단 여부는 selectionIssues가 따로 정한다. */
export function cardWarnings(
  choice: ModelChoice | undefined,
  input: { hasImages: boolean; hasSchema: boolean },
): string[] {
  if (!choice) return ["고를 수 없는 모델이에요. 모델을 다시 골라 주세요."];
  if (!choice.selectable)
    return [choice.unavailableReason ?? "지금은 고를 수 없는 모델이에요."];
  const warnings: string[] = [];
  if (input.hasImages && !choice.supportsImages)
    warnings.push(
      "이미지 입력을 지원하지 않아요. 이미지를 빼거나 모델을 바꿔 주세요.",
    );
  if (input.hasSchema && !supportsStructuredOutput(choice))
    warnings.push(
      "JSON Schema 출력을 지원하지 않아요. Schema를 비우거나 모델을 바꿔 주세요.",
    );
  return warnings;
}

export function inputSummary(values: {
  prompt: string;
  text: string;
  imageCount: number;
  jsonSchema: string;
}): string {
  const length = (value: string) => formatCount(Array.from(value).length);
  return [
    `Prompt ${length(values.prompt)}자`,
    values.text ? `입력 텍스트 ${length(values.text)}자` : "입력 텍스트 없음",
    values.imageCount > 0
      ? `이미지 ${formatCount(values.imageCount)}장`
      : "이미지 없음",
    values.jsonSchema.trim() ? "Schema 있음" : "Schema 없음",
  ].join(" · ");
}

/** 실행 버튼이 비활성일 때 옆에 적는 이유. 실행할 수 있으면 없다. */
export function runBlockReason(count: number): string | undefined {
  if (count < MODEL_LIMITS.min)
    return `모델을 ${MODEL_LIMITS.min - count}개 더 고르면 실행할 수 있어요`;
  if (count > MODEL_LIMITS.max)
    return `모델은 최대 ${MODEL_LIMITS.max}개까지 비교할 수 있어요`;
  return undefined;
}

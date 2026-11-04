import { z } from "zod";
import { MAX_TOKENS, TEMPERATURE } from "./limits";

export const comparisonSchema = z.object({
  comparisonId: z.string().min(1),
  modelKey: z.string().min(1, "비교 모델을 선택하시기 바랍니다."),
  settings: z
    .object({
      mode: z.enum(["shared", "custom"]),
      temperature: z.string(),
      maxTokens: z.string(),
      reasoningEffort: z.string(),
    })
    .superRefine((settings, context) => {
      if (settings.mode !== "custom") return;
      for (const key of ["temperature", "maxTokens"] as const) {
        if (!settings[key].trim()) continue;
        const value = Number(settings[key]);
        if (
          !Number.isFinite(value) ||
          (key === "temperature"
            ? value < TEMPERATURE.min || value > TEMPERATURE.max
            : !Number.isSafeInteger(value) || value < 1 || value > MAX_TOKENS)
        )
          context.addIssue({
            code: "custom",
            path: [key],
            message:
              key === "temperature"
                ? `${TEMPERATURE.min}~${TEMPERATURE.max} 사이의 숫자를 입력하시기 바랍니다.`
                : `1~${MAX_TOKENS.toLocaleString("ko-KR")} 사이의 정수를 입력하시기 바랍니다.`,
          });
      }
    })
    .transform((settings) => ({
      mode: settings.mode,
      temperature:
        settings.mode === "custom" && settings.temperature.trim()
          ? Number(settings.temperature)
          : undefined,
      maxTokens:
        settings.mode === "custom" && settings.maxTokens.trim()
          ? Number(settings.maxTokens)
          : undefined,
      reasoningEffort:
        settings.mode === "custom" && settings.reasoningEffort
          ? settings.reasoningEffort
          : undefined,
    })),
});

export type ComparisonValues = z.input<typeof comparisonSchema>;
export type ComparisonDraft = z.output<typeof comparisonSchema>;
export type RequestedSettings = Partial<
  Omit<ComparisonDraft["settings"], "mode">
>;

export function createComparison(
  modelKey: string,
  comparisonId: string = crypto.randomUUID(),
): ComparisonValues {
  return {
    comparisonId,
    modelKey,
    settings: {
      mode: "shared",
      temperature: "",
      maxTokens: "",
      reasoningEffort: "",
    },
  };
}

/**
 * 공통 설정을 켰을 때만 공통값을 돌려준다.
 * null은 공통 끔이며 요청의 execution_config: null과 같은 뜻이다.
 */
export function commonSettings(
  draft: RequestedSettings & { commonEnabled: boolean },
): RequestedSettings | null {
  if (!draft.commonEnabled) return null;
  return {
    temperature: draft.temperature,
    maxTokens: draft.maxTokens,
    reasoningEffort: draft.reasoningEffort,
  };
}

/**
 * 칸 하나에 요청할 설정을 모델별 지정값, 공통값, 시나리오 기본값 순으로 정한다.
 * common이 null(공통 끔)이면 서버와 같이 공통값과 시나리오 기본값을 물려주지 않는다.
 */
export function requestedSettings(
  comparison: ComparisonDraft,
  common: RequestedSettings | null,
  scenario: RequestedSettings = {},
): RequestedSettings {
  const own: RequestedSettings =
    comparison.settings.mode === "custom" ? comparison.settings : {};
  const inherited: RequestedSettings =
    common === null
      ? {}
      : {
          temperature: common.temperature ?? scenario.temperature,
          maxTokens: common.maxTokens ?? scenario.maxTokens,
          reasoningEffort: common.reasoningEffort ?? scenario.reasoningEffort,
        };
  const values = {
    temperature: own.temperature ?? inherited.temperature,
    maxTokens: own.maxTokens ?? inherited.maxTokens,
    reasoningEffort: own.reasoningEffort ?? inherited.reasoningEffort,
  };
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined),
  );
}

/** 모델별 설정을 켠 칸이 하나라도 있으면 공통 설정을 켤 수 없다. */
export function hasCustomComparison(
  comparisons: readonly { settings: { mode: string } }[],
) {
  return comparisons.some(
    (comparison) => comparison.settings.mode === "custom",
  );
}

export function comparisonCounts(comparisons: readonly { modelKey: string }[]) {
  const counts: Record<string, number> = {};
  for (const comparison of comparisons)
    if (comparison.modelKey)
      counts[comparison.modelKey] = (counts[comparison.modelKey] ?? 0) + 1;
  return counts;
}

export function selectedComparisonCount(
  keys: string[],
  counts: Readonly<Record<string, number>> = {},
) {
  return keys.reduce((sum, key) => sum + (counts[key] ?? 1), 0);
}

export function reconcileComparisons(
  current: ComparisonValues[],
  keys: string[],
  newId: () => string = () => crypto.randomUUID(),
) {
  const retained = current.filter((comparison) =>
    keys.includes(comparison.modelKey),
  );
  const added = keys
    .filter((key) => !current.some((comparison) => comparison.modelKey === key))
    .map((key) => createComparison(key, newId()));
  return [...retained, ...added];
}

// 기존 데이터는 불러올 때 비교 항목으로 변환하고 이후에는 항목 ID로 편집한다.
export function createComparisons(keys: string[]) {
  return keys
    .filter(Boolean)
    .map((key, index) => createComparison(key, `comparison-${index + 1}`));
}

import { z } from "zod";
import { comparisonSchema } from "./comparisons";
import { imageCountMessage, imageFilesSchemaFor } from "./images";
import {
  IMAGE_LIMITS,
  type ImageLimits,
  MAX_TOKENS,
  MODEL_LIMITS,
  TEMPERATURE,
  TEXT_LIMIT,
} from "./limits";
import { parameterIssue } from "./parameters";
import type { ModelChoice } from "./presentation";

const TEMPERATURE_MESSAGE = `${TEMPERATURE.min}~${TEMPERATURE.max} 사이의 숫자를 입력해 주세요.`;
const MAX_TOKENS_LIMIT_MESSAGE = `${MAX_TOKENS.toLocaleString("ko-KR")} 이하로 입력해 주세요.`;
const MAX_TOKENS_INTEGER_MESSAGE = "1 이상의 정수를 입력해 주세요.";

function toOptionalNumber(value: string) {
  return value.trim() === "" ? undefined : Number(value);
}

function temperatureIssue(value: number | undefined) {
  if (value === undefined) return undefined;
  return Number.isFinite(value) &&
    value >= TEMPERATURE.min &&
    value <= TEMPERATURE.max
    ? undefined
    : TEMPERATURE_MESSAGE;
}

function maxTokensIssue(value: number | undefined) {
  if (value === undefined) return undefined;
  // NaN·Infinity도 상한 문구로 거절한다(기존 동작과 같음).
  if (!(value <= MAX_TOKENS)) return MAX_TOKENS_LIMIT_MESSAGE;
  return Number.isSafeInteger(value) && value >= 1
    ? undefined
    : MAX_TOKENS_INTEGER_MESSAGE;
}

const text = z
  .string()
  .max(
    TEXT_LIMIT,
    `${TEXT_LIMIT.toLocaleString("ko-KR")}자 이내로 입력해 주세요.`,
  );

function validJsonSchema(value: string) {
  if (!value.trim()) return true;
  try {
    const parsed: unknown = JSON.parse(value);
    return (
      typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
    );
  } catch {
    return false;
  }
}

const createFormSchema = (limits: ImageLimits) =>
  z
    .object({
      mode: z.enum(["custom", "scenario"]),
      scenarioKey: z.string(),
      prompt: text.refine(
        (value) => value.trim().length > 0,
        "Prompt를 입력해 주세요.",
      ),
      text,
      jsonSchema: z
        .string()
        .refine(validJsonSchema, "JSON 객체 형식의 Schema를 입력해 주세요."),
      // 끄면 공통값과 시나리오 기본값을 모두 쓰지 않는다. 요청에는 execution_config: null로 보낸다.
      commonEnabled: z.boolean().default(false),
      // 공통값은 켜져 있을 때만 검사하므로 범위 검사는 아래 superRefine에서 한다.
      // 항목은 숫자 변환만 한다. AI 도우미(assistant.ts)가 shape의 이 변환을 그대로 쓴다.
      temperature: z.string().transform(toOptionalNumber),
      maxTokens: z.string().transform(toOptionalNumber),
      reasoningEffort: z
        .string()
        .trim()
        .transform((value) => value || undefined),
      comparisons: z
        .array(comparisonSchema)
        .min(MODEL_LIMITS.min, "비교 항목을 2개 이상 골라 주세요.")
        .max(MODEL_LIMITS.max, "비교 항목은 최대 4개까지 추가할 수 있어요.")
        .refine(
          (values) =>
            new Set(values.map((item) => item.comparisonId)).size ===
            values.length,
          "비교 항목 식별자는 서로 달라야 해요.",
        ),
      files: imageFilesSchemaFor(limits),
      // 재실행에서 그대로 다시 쓰는 이미지. 파일을 다시 올리지 않는다.
      existingAssetIds: z.array(z.string()),
    })
    .superRefine((values, context) => {
      if (values.mode === "scenario" && !values.scenarioKey)
        context.addIssue({
          code: "custom",
          path: ["scenarioKey"],
          message: "시나리오를 골라 주세요.",
        });
      if (
        values.files.length + values.existingAssetIds.length >
        limits.maxCount
      )
        context.addIssue({
          code: "custom",
          path: ["files"],
          message: imageCountMessage(limits),
        });
      if (!values.commonEnabled) return;
      const commonIssues = [
        ["temperature", temperatureIssue(values.temperature)],
        ["maxTokens", maxTokensIssue(values.maxTokens)],
      ] as const;
      for (const [path, message] of commonIssues)
        if (message)
          context.addIssue({ code: "custom", path: [path], message });
    });
// 끝에 transform을 두지 않는다. 객체 스키마가 유지되어야 shape를 쓸 수 있다.
// 꺼진 공통값은 commonSettings()와 toCreateRequest()가 쓰지 않는다.

export const simulatorFormSchema = createFormSchema(IMAGE_LIMITS);

export type SimulatorFormValues = z.input<typeof simulatorFormSchema>;
export type SimulatorDraft = z.output<typeof simulatorFormSchema>;

export function simulatorSchemaFor(
  choices: ModelChoice[],
  limits: ImageLimits = IMAGE_LIMITS,
) {
  return createFormSchema(limits).superRefine((draft, context) => {
    draft.comparisons.forEach((comparison, index) => {
      if (comparison.settings.mode !== "custom") return;
      const choice = choices.find((item) => item.key === comparison.modelKey);
      if (!choice) return;
      for (const key of [
        "temperature",
        "maxTokens",
        "reasoningEffort",
      ] as const) {
        const value = comparison.settings[key];
        if (value === undefined) continue;
        const parameter = choice.tuningParameters?.find(
          (item) => item.key === key,
        );
        const message = parameter
          ? parameterIssue(parameter, value)
          : "모델별 설정 지원 정보를 확인할 수 없어요.";
        if (message)
          context.addIssue({
            code: "custom",
            path: ["comparisons", index, "settings", key],
            message,
          });
      }
    });
  });
}

export function createDefaultValues(
  initialValues?: Partial<SimulatorFormValues>,
): SimulatorFormValues {
  return {
    mode: "custom",
    scenarioKey: "",
    prompt: "",
    text: "",
    jsonSchema: "",
    commonEnabled: false,
    temperature: "",
    maxTokens: "",
    reasoningEffort: "",
    files: [],
    existingAssetIds: [],
    ...initialValues,
    comparisons:
      initialValues?.comparisons?.map((item) => ({
        ...item,
        settings: { ...item.settings },
      })) ?? [],
  };
}

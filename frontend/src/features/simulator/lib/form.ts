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

const optionalNumber = (valid: (value: number) => boolean, message: string) =>
  z
    .string()
    .refine(
      (value) =>
        value.trim() === "" ||
        (Number.isFinite(Number(value)) && valid(Number(value))),
      message,
    )
    .transform((value) => (value.trim() === "" ? undefined : Number(value)));

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
      temperature: optionalNumber(
        (value) => value >= TEMPERATURE.min && value <= TEMPERATURE.max,
        `${TEMPERATURE.min}~${TEMPERATURE.max} 사이의 숫자를 입력해 주세요.`,
      ),
      maxTokens: z
        .string()
        .refine(
          (value) => value.trim() === "" || Number(value) <= MAX_TOKENS,
          `${MAX_TOKENS.toLocaleString("ko-KR")} 이하로 입력해 주세요.`,
        )
        .pipe(
          optionalNumber(
            (value) => Number.isSafeInteger(value) && value >= 1,
            "1 이상의 정수를 입력해 주세요.",
          ),
        ),
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
    });

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

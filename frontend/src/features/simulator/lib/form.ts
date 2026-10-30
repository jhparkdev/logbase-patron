import { z } from "zod";
import { imageFilesSchema } from "./images";
import { MODEL_LIMITS, TEMPERATURE, TEXT_LIMIT } from "./limits";

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
      typeof parsed === "boolean" ||
      (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed))
    );
  } catch {
    return false;
  }
}

export const simulatorFormSchema = z
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
      .refine(
        validJsonSchema,
        "JSON 객체 또는 true·false 형식의 Schema를 입력해 주세요.",
      ),
    temperature: optionalNumber(
      (value) => value >= TEMPERATURE.min && value <= TEMPERATURE.max,
      `${TEMPERATURE.min}~${TEMPERATURE.max} 사이의 숫자를 입력해 주세요.`,
    ),
    maxTokens: optionalNumber(
      (value) => Number.isSafeInteger(value) && value >= 1,
      "1 이상의 정수를 입력해 주세요.",
    ),
    selections: z
      .array(z.string().min(1, "비교 모델을 선택해 주세요."))
      .min(MODEL_LIMITS.min, "모델을 2개 이상 선택해 주세요.")
      .max(MODEL_LIMITS.max, "모델은 최대 4개까지 선택할 수 있어요.")
      .refine(
        (values) => new Set(values).size === values.length,
        "같은 모델과 Provider는 한 번만 선택해 주세요.",
      ),
    files: imageFilesSchema,
  })
  .superRefine((values, context) => {
    if (values.mode === "scenario" && !values.scenarioKey)
      context.addIssue({
        code: "custom",
        path: ["scenarioKey"],
        message: "시나리오를 선택해 주세요.",
      });
  });

export type SimulatorFormValues = z.input<typeof simulatorFormSchema>;
export type SimulatorDraft = z.output<typeof simulatorFormSchema>;

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
    files: [],
    ...initialValues,
    selections: initialValues?.selections?.filter(Boolean) ?? [],
  };
}

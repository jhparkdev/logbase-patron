import { z } from "zod";
import type { components } from "../../../shared/api/schema";
import type { ComparisonValues } from "./comparisons";
import type { ModelChoice } from "./presentation";

type Schemas = components["schemas"];
type OutputType = Schemas["OutputType"];
type ImageQuality = Schemas["ImageQuality"];

export const OUTPUT_TYPE_LABELS: Record<OutputType, string> = {
  TEXT: "텍스트",
  IMAGE: "이미지",
};
const OUTPUT_TYPES = ["TEXT", "IMAGE"] as const satisfies readonly OutputType[];

// 백엔드 ImageConfig.n 범위(OpenAPI minimum·maximum)와 같은 값이다. 넘으면 서버가 거절한다.
export const IMAGE_COUNT = { min: 1, max: 4 } as const;

export const IMAGE_QUALITY_LABELS: Record<ImageQuality, string> = {
  auto: "자동",
  low: "낮음",
  medium: "보통",
  high: "높음",
};
const IMAGE_QUALITIES = [
  "auto",
  "low",
  "medium",
  "high",
] as const satisfies readonly ImageQuality[];

const MODEL_DEFAULT = { value: "", label: "모델 기본값" };
export const OUTPUT_TYPE_OPTIONS = OUTPUT_TYPES.map((value) => ({
  value,
  label: OUTPUT_TYPE_LABELS[value],
}));
export const IMAGE_COUNT_OPTIONS = [
  MODEL_DEFAULT,
  ...Array.from(
    { length: IMAGE_COUNT.max - IMAGE_COUNT.min + 1 },
    (_, index) => {
      const count = String(IMAGE_COUNT.min + index);
      return { value: count, label: `${count}장` };
    },
  ),
];
export const IMAGE_QUALITY_OPTIONS = [
  MODEL_DEFAULT,
  ...IMAGE_QUALITIES.map((value) => ({
    value,
    label: IMAGE_QUALITY_LABELS[value],
  })),
];

const IMAGE_COUNT_MESSAGE = `${IMAGE_COUNT.min}~${IMAGE_COUNT.max}장 중에서 골라 주세요.`;
const DUPLICATE_MESSAGE =
  "이미지 생성은 모든 칸에 같은 옵션을 보내요. 같은 모델·업체는 한 번만 골라 주세요.";

function validImageCount(value: string) {
  if (value === "") return true;
  const count = Number(value);
  return (
    Number.isSafeInteger(count) &&
    count >= IMAGE_COUNT.min &&
    count <= IMAGE_COUNT.max
  );
}

/** 시뮬레이터 폼에 펼쳐 넣는 출력 형식 필드. 이미지 옵션을 비우면 모델 기본값을 쓴다. */
export const outputFields = {
  outputType: z.enum(OUTPUT_TYPES).default("TEXT"),
  imageCount: z
    .string()
    .default("")
    .refine(validImageCount, IMAGE_COUNT_MESSAGE)
    .transform((value) => (value === "" ? undefined : Number(value))),
  imageQuality: z
    .union([z.literal(""), z.enum(IMAGE_QUALITIES)])
    .default("")
    .transform((value) => value || undefined),
};

type OutputDraft = {
  outputType: OutputType;
  imageCount: number | undefined;
  imageQuality: ImageQuality | undefined;
};

export function toImageConfig(
  draft: OutputDraft,
): Schemas["ImageConfig"] | undefined {
  if (draft.outputType !== "IMAGE") return undefined;
  return {
    ...(draft.imageCount !== undefined ? { n: draft.imageCount } : {}),
    ...(draft.imageQuality ? { quality: draft.imageQuality } : {}),
  };
}

export function choicesForOutput(
  choices: ModelChoice[],
  outputType: OutputType,
): ModelChoice[] {
  if (outputType !== "IMAGE") return choices;
  return choices.filter((choice) => choice.generatesImages);
}

/** 서버가 접수에서 거절할 조합을 비용이 나가기 전에 알려 준다. */
export function imageOutputIssues(
  draft: {
    outputType: OutputType;
    comparisons: readonly Pick<ComparisonValues, "modelKey">[];
  },
  choices: ModelChoice[],
): string[] {
  if (draft.outputType !== "IMAGE") return [];
  const keys = draft.comparisons.map((item) => item.modelKey);
  const issues = keys.flatMap((key) => {
    const choice = choices.find((item) => item.key === key);
    return choice && !choice.generatesImages
      ? [`${choice.name}은 이미지를 만들지 못해요.`]
      : [];
  });
  if (new Set(keys).size !== keys.length) issues.push(DUPLICATE_MESSAGE);
  return issues;
}

export function outputImageUrl(outputAssetId: string): string {
  return `/api/simulations/output-images/${outputAssetId}`;
}

import { expect, test } from "vitest";
import { z } from "zod";
import { createComparisons } from "./comparisons";
import {
  choicesForOutput,
  IMAGE_COUNT,
  imageOutputIssues,
  outputFields,
  outputImageUrl,
  toImageConfig,
} from "./output";
import type { ModelChoice } from "./presentation";

const schema = z.object(outputFields);

function choice(key: string, generatesImages?: boolean): ModelChoice {
  return {
    key,
    name: `모델 ${key}`,
    provider: "Google",
    selectable: true,
    supportsImages: true,
    supportedParameters: [],
    ...(generatesImages === undefined ? {} : { generatesImages }),
  };
}

const IMAGE_MODEL = choice("6:Google", true);
const OTHER_IMAGE_MODEL = choice("7:Google", true);
const TEXT_MODEL = choice("2:DeepInfra", false);

test("출력 형식은 처음에 텍스트이고 이미지 옵션은 비어 있다", () => {
  expect(schema.parse({})).toEqual({
    outputType: "TEXT",
    imageCount: undefined,
    imageQuality: undefined,
  });
});

test("장 수는 1장 바로 전·1장·최대·최대 바로 후를 구분한다", () => {
  const count = (value: string) =>
    schema.safeParse({ outputType: "IMAGE", imageCount: value });
  expect(count(String(IMAGE_COUNT.min - 1)).success).toBe(false);
  expect(count(String(IMAGE_COUNT.min)).data?.imageCount).toBe(IMAGE_COUNT.min);
  expect(count(String(IMAGE_COUNT.max)).data?.imageCount).toBe(IMAGE_COUNT.max);
  expect(count(String(IMAGE_COUNT.max + 1)).success).toBe(false);
  expect(count("1.5").success).toBe(false);
});

test("품질은 서버 계약의 값만 받는다", () => {
  expect(schema.parse({ imageQuality: "high" }).imageQuality).toBe("high");
  expect(schema.safeParse({ imageQuality: "ultra" }).success).toBe(false);
});

test("이미지 옵션은 이미지 출력일 때만 만들고 비운 항목은 보내지 않는다", () => {
  expect(
    toImageConfig({
      outputType: "TEXT",
      imageCount: 2,
      imageQuality: "low",
    }),
  ).toBeUndefined();
  expect(
    toImageConfig({
      outputType: "IMAGE",
      imageCount: undefined,
      imageQuality: undefined,
    }),
  ).toEqual({});
  expect(
    toImageConfig({ outputType: "IMAGE", imageCount: 2, imageQuality: "low" }),
  ).toEqual({ n: 2, quality: "low" });
});

test("이미지 출력이면 이미지를 만드는 모델만 고를 수 있게 거른다", () => {
  const choices = [IMAGE_MODEL, TEXT_MODEL, choice("9:Unknown")];
  expect(choicesForOutput(choices, "TEXT")).toBe(choices);
  expect(choicesForOutput(choices, "IMAGE")).toEqual([IMAGE_MODEL]);
});

test("이미지 출력에서 이미지를 못 만드는 모델과 같은 모델·업체 두 칸을 실행 전에 막는다", () => {
  const choices = [IMAGE_MODEL, OTHER_IMAGE_MODEL, TEXT_MODEL];
  const issues = (outputType: "TEXT" | "IMAGE", keys: string[]) =>
    imageOutputIssues(
      { outputType, comparisons: createComparisons(keys) },
      choices,
    );
  expect(issues("TEXT", ["2:DeepInfra", "2:DeepInfra"])).toEqual([]);
  expect(issues("IMAGE", ["6:Google", "7:Google"])).toEqual([]);
  expect(issues("IMAGE", ["6:Google", "2:DeepInfra"])).toEqual([
    "모델 2:DeepInfra은 이미지를 만들지 못해요.",
  ]);
  expect(issues("IMAGE", ["6:Google", "6:Google"])).toEqual([
    "이미지 생성은 모든 칸에 같은 옵션을 보내요. 같은 모델·업체는 한 번만 골라 주세요.",
  ]);
});

test("결과 이미지는 서버를 거쳐 받는 상대 경로를 쓴다", () => {
  expect(outputImageUrl("01a1a48c-7804-73a5-8265-5ab816b18b09")).toBe(
    "/api/simulations/output-images/01a1a48c-7804-73a5-8265-5ab816b18b09",
  );
});

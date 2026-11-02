import { describe, expect, test } from "vitest";
import { createComparisons } from "./comparisons";
import { createDefaultValues, simulatorFormSchema } from "./form";
import { IMAGE_LIMITS, TEXT_LIMIT } from "./limits";

const valid = () => ({
  ...createDefaultValues(),
  prompt: "원문을 보존해 주세요. ",
  comparisons: createComparisons(["a", "b"]),
});

describe("시뮬레이터 입력 경계", () => {
  test.each([1999, 2000, 2001])("텍스트 %i자", (length) => {
    const values = {
      ...valid(),
      prompt: "가".repeat(length),
      text: "나".repeat(length),
    };
    expect(simulatorFormSchema.safeParse(values).success).toBe(
      length <= TEXT_LIMIT,
    );
  });
  test("이모지도 글자 수와 검증에서 한 글자로 센다", () => {
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        prompt: "😀".repeat(TEXT_LIMIT),
      }).success,
    ).toBe(true);
  });
  test.each([1, 2, 4, 5])("모델 %i개", (length) => {
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        comparisons: createComparisons(
          Array.from({ length }, (_, i) => `${i}`),
        ),
      }).success,
    ).toBe(length >= 2 && length <= 4);
  });
  test("빈 모델과 중복된 비교 항목 식별자는 제출하지 않는다", () => {
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        comparisons: createComparisons(["a", ""]),
      }).success,
    ).toBe(false);
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        comparisons: [...createComparisons(["a"]), ...createComparisons(["a"])],
      }).success,
    ).toBe(false);
  });
  test("빈 고급 설정은 기본값 사용으로 남기고 Prompt 원문을 유지한다", () => {
    const result = simulatorFormSchema.parse(valid());
    expect(result.temperature).toBeUndefined();
    expect(result.maxTokens).toBeUndefined();
    expect(result.reasoningEffort).toBeUndefined();
    expect(result.prompt).toBe(valid().prompt);
  });
  test("공통 effort를 제출값과 복원 입력에 보존한다", () => {
    const values = { ...valid(), reasoningEffort: "high" };
    expect(simulatorFormSchema.parse(values).reasoningEffort).toBe("high");
    expect(createDefaultValues(values).reasoningEffort).toBe("high");
  });
  test.each(["-0.01", "2.01", "NaN"])("Temperature %s 거절", (temperature) => {
    expect(
      simulatorFormSchema.safeParse({ ...valid(), temperature }).success,
    ).toBe(false);
  });
  test.each(["0", "0.01", "2"])("Temperature %s 허용", (temperature) => {
    expect(
      simulatorFormSchema.safeParse({ ...valid(), temperature }).success,
    ).toBe(true);
  });
  test.each(["0", "-1", "1.5", "Infinity"])(
    "출력 토큰 %s 거절",
    (maxTokens) => {
      expect(
        simulatorFormSchema.safeParse({ ...valid(), maxTokens }).success,
      ).toBe(false);
    },
  );
  test.each([
    ["4095", true],
    ["4096", true],
    ["4097", false],
  ])("출력 토큰 상한 경계 %s", (maxTokens, ok) => {
    expect(
      simulatorFormSchema.safeParse({ ...valid(), maxTokens }).success,
    ).toBe(ok);
  });
  test("재실행 이미지와 새 파일을 합쳐 개수 한도를 검사한다", () => {
    const png = new File(["image"], "image.png", { type: "image/png" });
    const existingAssetIds = Array(IMAGE_LIMITS.maxCount).fill("asset");
    expect(
      simulatorFormSchema.safeParse({ ...valid(), existingAssetIds }).success,
    ).toBe(true);
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        existingAssetIds,
        files: [png],
      }).success,
    ).toBe(false);
  });
  test("JSON Schema는 서버 계약대로 JSON 객체만 받고, 비어 있으면 미지정", () => {
    for (const jsonSchema of ["", "{}"])
      expect(
        simulatorFormSchema.safeParse({ ...valid(), jsonSchema }).success,
      ).toBe(true);
    for (const jsonSchema of ["{", "[]", '"text"', "true", "false"])
      expect(
        simulatorFormSchema.safeParse({ ...valid(), jsonSchema }).success,
      ).toBe(false);
  });
  test.each([
    IMAGE_LIMITS.maxBytes - 1,
    IMAGE_LIMITS.maxBytes,
    IMAGE_LIMITS.maxBytes + 1,
  ])("파일 %i bytes", (size) => {
    const file = new File([new Uint8Array(size)], "image.png", {
      type: "image/png",
    });
    expect(
      simulatorFormSchema.safeParse({ ...valid(), files: [file] }).success,
    ).toBe(size <= IMAGE_LIMITS.maxBytes);
  });
  test("이미지 형식·개수·빈 파일을 검사한다", () => {
    const png = new File(["image"], "image.png", { type: "image/png" });
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        files: Array(IMAGE_LIMITS.maxCount).fill(png),
      }).success,
    ).toBe(true);
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        files: Array(IMAGE_LIMITS.maxCount + 1).fill(png),
      }).success,
    ).toBe(false);
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        files: [new File(["svg"], "image.svg", { type: "image/svg+xml" })],
      }).success,
    ).toBe(false);
    expect(
      simulatorFormSchema.safeParse({
        ...valid(),
        files: [new File([], "image.png", { type: "image/png" })],
      }).success,
    ).toBe(false);
  });
});

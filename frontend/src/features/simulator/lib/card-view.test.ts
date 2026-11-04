import { expect, test } from "vitest";
import {
  cardWarnings,
  inputSummary,
  resolvedSettings,
  runBlockReason,
  unitPriceLabel,
} from "./card-view";
import { createComparison } from "./comparisons";
import type { ModelChoice } from "./presentation";

const choice: ModelChoice = {
  key: "a:p",
  name: "모델 A",
  provider: "p",
  selectable: true,
  supportsImages: false,
  supportedParameters: ["temperature", "max_tokens", "reasoning"],
  tuningParameters: [
    { key: "temperature", kind: "number", min: 0, max: 2, step: 0.01 },
    { key: "maxTokens", kind: "number", min: 1, max: 4096, step: 1 },
    {
      key: "reasoningEffort",
      kind: "choice",
      options: [
        { value: "low", label: "낮음" },
        { value: "high", label: "높음" },
      ],
    },
  ],
  price: { input: "0.0000006", output: "0.0000025" },
};
const empty = { temperature: "", maxTokens: "", reasoningEffort: "" };

test("단가는 100만 토큰당으로 보여 주고 하나라도 없으면 미확인으로 둔다", () => {
  expect(unitPriceLabel(choice.price)).toBe("입력 0.60 · 출력 2.50");
  expect(unitPriceLabel(undefined)).toBeNull();
  expect(unitPriceLabel({ input: null, output: "0.0000025" })).toBeNull();
});

test("카드에는 실제 전송될 값과 그 출처를 공통·시나리오·기본값 순으로 보여 준다", () => {
  const common = { ...empty, temperature: "0.7" };
  expect(
    resolvedSettings(
      createComparison("a:p"),
      common,
      { maxTokens: 512 },
      choice,
    ),
  ).toEqual([
    {
      key: "temperature",
      label: "Temperature",
      value: "0.7",
      source: "common",
    },
    {
      key: "maxTokens",
      label: "최대 출력 토큰",
      value: "512",
      source: "scenario",
    },
    {
      key: "reasoningEffort",
      label: "추론 강도",
      value: "기본값",
      source: "default",
    },
  ]);
});

test("개별 설정은 공통값보다 우선하고 선택지는 이름으로 보여 준다", () => {
  const custom = createComparison("a:p");
  custom.settings = {
    mode: "custom",
    temperature: "0.2",
    maxTokens: "1024",
    reasoningEffort: "high",
  };
  expect(
    resolvedSettings(
      custom,
      { ...empty, temperature: "0.7" },
      undefined,
      choice,
    ),
  ).toEqual([
    {
      key: "temperature",
      label: "Temperature",
      value: "0.2",
      source: "custom",
    },
    {
      key: "maxTokens",
      label: "최대 출력 토큰",
      value: "1,024",
      source: "custom",
    },
    {
      key: "reasoningEffort",
      label: "추론 강도",
      value: "높음",
      source: "custom",
    },
  ]);
  // 개별 설정을 켰어도 비워 둔 칸은 공통값을 따른다
  custom.settings.temperature = "";
  expect(
    resolvedSettings(
      custom,
      { ...empty, temperature: "0.7" },
      undefined,
      choice,
    )[0],
  ).toMatchObject({ value: "0.7", source: "common" });
});

test("모델이 지원하지 않는 설정은 값이 있어도 미지원으로 표시한다", () => {
  const noEffort = {
    ...choice,
    tuningParameters: choice.tuningParameters?.filter(
      (item) => item.key !== "reasoningEffort",
    ),
  };
  expect(
    resolvedSettings(
      createComparison("a:p"),
      { ...empty, reasoningEffort: "high" },
      undefined,
      noEffort,
    )[2],
  ).toEqual({
    key: "reasoningEffort",
    label: "추론 강도",
    value: "미지원",
    source: "unsupported",
  });
  // 지원 정보가 없는 모델은 값을 그대로 보여 준다
  expect(
    resolvedSettings(
      createComparison("a:p"),
      { ...empty, reasoningEffort: "high" },
      undefined,
      undefined,
    )[2],
  ).toMatchObject({ value: "high", source: "common" });
});

test("이미지·Schema 충돌과 고를 수 없는 사유를 카드에서 바로 알린다", () => {
  expect(cardWarnings(choice, { hasImages: false, hasSchema: false })).toEqual(
    [],
  );
  expect(cardWarnings(choice, { hasImages: true, hasSchema: true })).toEqual([
    "이미지 입력을 지원하지 않아요. 이미지를 빼거나 모델을 바꿔 주세요.",
    "JSON Schema 출력을 지원하지 않아요. Schema를 비우거나 모델을 바꿔 주세요.",
  ]);
  expect(
    cardWarnings(
      {
        ...choice,
        supportsImages: true,
        supportedParameters: ["response_format"],
      },
      { hasImages: true, hasSchema: true },
    ),
  ).toEqual([]);
  expect(
    cardWarnings(
      { ...choice, selectable: false, unavailableReason: "비활성 모델" },
      { hasImages: false, hasSchema: false },
    ),
  ).toEqual(["비활성 모델"]);
  expect(
    cardWarnings(undefined, { hasImages: false, hasSchema: false }),
  ).toEqual(["고를 수 없는 모델이에요. 모델을 다시 골라 주세요."]);
});

test("실행 조건을 한 줄로 요약한다", () => {
  expect(
    inputSummary({
      prompt: "가".repeat(96),
      text: "",
      imageCount: 1,
      jsonSchema: "",
    }),
  ).toBe("Prompt 96자 · 입력 텍스트 없음 · 이미지 1장 · Schema 없음");
  expect(
    inputSummary({ prompt: "", text: "나나", imageCount: 0, jsonSchema: "{}" }),
  ).toBe("Prompt 0자 · 입력 텍스트 2자 · 이미지 없음 · Schema 있음");
});

test.each([
  [0, "모델을 2개 더 고르면 실행할 수 있어요"],
  [1, "모델을 1개 더 고르면 실행할 수 있어요"],
  [2, undefined],
  [4, undefined],
  [5, "모델은 최대 4개까지 비교할 수 있어요"],
])("모델 %i개일 때 실행 버튼 옆 안내", (count, reason) => {
  expect(runBlockReason(count)).toBe(reason);
});

test("이미지 출력이면 이미지를 못 만드는 모델 카드에 경고한다", () => {
  const input = { hasImages: false, hasSchema: false, imageOutput: true };
  expect(cardWarnings(choice, input)).toEqual([
    "이미지를 만들지 못해요. 출력 형식을 텍스트로 바꾸거나 모델을 바꿔 주세요.",
  ]);
  expect(cardWarnings({ ...choice, generatesImages: true }, input)).toEqual([]);
});

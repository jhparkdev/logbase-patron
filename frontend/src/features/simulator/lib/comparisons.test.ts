import { expect, test } from "vitest";
import {
  createComparison,
  reconcileComparisons,
  requestedSettings,
  selectedComparisonCount,
} from "./comparisons";
import { createDefaultValues, simulatorFormSchema } from "./form";
import { type ModelChoice, selectionIssues } from "./presentation";

const choice: ModelChoice = {
  key: "a:p",
  name: "모델 A",
  provider: "p",
  selectable: true,
  supportsImages: false,
  supportedParameters: ["temperature", "max_tokens", "reasoning"],
  tuningParameters: [
    { key: "temperature", kind: "number", min: 0, max: 1, step: 0.1 },
    { key: "maxTokens", kind: "number", min: 1, max: 1024, step: 1 },
    {
      key: "reasoningEffort",
      kind: "choice",
      options: [
        { value: "low", label: "낮음" },
        { value: "high", label: "높음" },
      ],
    },
  ],
};
function draft(secondTemperature = "0.7") {
  const first = createComparison(choice.key, "first");
  const second = createComparison(choice.key, "second");
  second.settings = {
    mode: "custom",
    temperature: secondTemperature,
    maxTokens: "",
    reasoningEffort: "",
  };
  return simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    temperature: "0.3",
    comparisons: [first, second],
  });
}

test("같은 모델·Provider라도 요청 설정이 다르면 비교하고 숫자 표기만 다른 중복은 막는다", () => {
  expect(selectionIssues(draft(), [choice], [])).toEqual([]);
  expect(selectionIssues(draft("0.30"), [choice], []).join(" ")).toContain(
    "요청 설정이 같은",
  );
});

test("모델별 지정값, 공통 설정, 시나리오 기본값 순으로 요청 설정을 구성한다", () => {
  const comparison = draft().comparisons[1];
  expect(
    requestedSettings(
      comparison,
      { temperature: 0.3 },
      { temperature: 0.1, maxTokens: 512 },
    ),
  ).toEqual({ temperature: 0.7, maxTokens: 512 });
  const shared = {
    ...comparison,
    settings: { ...comparison.settings, mode: "shared" as const },
  };
  expect(
    requestedSettings(
      shared,
      { temperature: 0.3 },
      { temperature: 0.1, maxTokens: 512 },
    ),
  ).toEqual({ temperature: 0.3, maxTokens: 512 });
});

test("검색 모달을 다시 적용해도 기존 식별자·개별 설정·복제 항목을 보존한다", () => {
  const first = createComparison("a:p", "first");
  const second = createComparison("a:p", "second");
  second.settings.temperature = "0.7";
  const removed = createComparison("b:p", "removed");
  const before = structuredClone([first, second, removed]);
  const result = reconcileComparisons(
    [first, second, removed],
    ["a:p", "c:p"],
    () => "new",
  );
  expect(result.map((item) => item.comparisonId)).toEqual([
    "first",
    "second",
    "new",
  ]);
  expect(result[1].settings.temperature).toBe("0.7");
  expect([first, second, removed]).toEqual(before);
  expect(selectedComparisonCount(["a:p", "c:p"], { "a:p": 2 })).toBe(3);
});

test("개별 설정을 꺼 두면 편집 중인 잘못된 값을 제출하지 않는다", () => {
  const comparison = createComparison(choice.key, "a");
  comparison.settings.temperature = "잘못된 값";
  const result = simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    comparisons: [comparison, createComparison("b:p", "b")],
  });
  expect(result.comparisons[0].settings.temperature).toBeUndefined();
});

test("모델별 범위·선택지와 현재 지원 정보를 실행 전에 다시 확인한다", () => {
  expect(selectionIssues(draft("1.1"), [choice], []).join(" ")).toContain(
    "0~1",
  );
  const configured = draft();
  configured.comparisons[1].settings.reasoningEffort = "unknown";
  expect(selectionIssues(configured, [choice], []).join(" ")).toContain(
    "추론 강도",
  );
  expect(
    selectionIssues(draft(), [{ ...choice, tuningParameters: [] }], []).join(
      " ",
    ),
  ).toContain("모델별 설정");
});

test("서로 다른 비교 항목 식별자를 요구한다", () => {
  const same = createComparison(choice.key, "same");
  expect(
    simulatorFormSchema.safeParse({
      ...createDefaultValues(),
      prompt: "작업",
      comparisons: [same, same],
    }).success,
  ).toBe(false);
});

test("Custom 입력에서는 이전에 고른 시나리오의 기본값을 적용하지 않는다", () => {
  const input = draft();
  input.temperature = undefined;
  input.scenarioKey = "previous";
  input.comparisons[1].settings.temperature = 0.7;
  const unsupported = {
    ...choice,
    supportedParameters: [],
    tuningParameters: [],
  };
  input.comparisons[1].modelKey = "b:p";
  expect(
    selectionIssues(
      input,
      [unsupported, { ...choice, key: "b:p" }],
      [
        {
          key: "previous",
          name: "이전 시나리오",
          prompt: "작업",
          imageRequired: false,
          schemaText: "",
          defaults: { temperature: 0.5 },
        },
      ],
    ),
  ).toEqual([]);
});

test("공통 effort는 항목별로 상속하고 개별 지정한 값만 우선한다", () => {
  const values = simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    reasoningEffort: "high",
    comparisons: [
      createComparison("a:p", "first"),
      createComparison("b:p", "second"),
    ],
  });
  expect(requestedSettings(values.comparisons[0], values)).toEqual({
    reasoningEffort: "high",
  });
  values.comparisons[1].settings.mode = "custom";
  values.comparisons[1].settings.reasoningEffort = "low";
  expect(requestedSettings(values.comparisons[1], values)).toEqual({
    reasoningEffort: "low",
  });
});

test("공통 effort 미지원·선택지 미확인·허용하지 않는 값은 실행하지 않는다", () => {
  const input = simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    reasoningEffort: "high",
    comparisons: [
      createComparison("a:p", "first"),
      createComparison("b:p", "second"),
    ],
  });
  expect(
    selectionIssues(
      input,
      [choice, { ...choice, key: "b:p", name: "모델 B" }],
      [],
    ),
  ).toEqual([]);
  expect(
    selectionIssues(
      input,
      [
        choice,
        {
          ...choice,
          key: "b:p",
          supportedParameters: [],
          tuningParameters: [],
        },
      ],
      [],
    ).join(" "),
  ).toContain("추론 강도");
  expect(
    selectionIssues(
      input,
      [choice, { ...choice, key: "b:p", tuningParameters: [] }],
      [],
    ).join(" "),
  ).toContain("선택지");
  expect(
    selectionIssues(
      input,
      [
        choice,
        {
          ...choice,
          key: "b:p",
          tuningParameters: [
            {
              key: "reasoningEffort",
              kind: "choice",
              options: [{ value: "low", label: "낮음" }],
            },
          ],
        },
      ],
      [],
    ).join(" "),
  ).toContain("추론 강도");
});

import { expect, test } from "vitest";
import { createComparisons } from "./comparisons";
import { createDefaultValues, simulatorFormSchema } from "./form";
import {
  appliedSettings,
  commonSettingsNote,
  comparisonModeLabel,
  type ModelChoice,
  type ScenarioChoice,
  selectionIssues,
} from "./presentation";

const model: ModelChoice = {
  key: "model:provider",
  name: "테스트 모델",
  provider: "실행 Provider",
  selectable: true,
  supportsImages: false,
  supportedParameters: [],
};
const draft = () =>
  simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    comparisons: createComparisons([model.key, "other:provider"]),
  });
const choices = () => [
  model,
  { ...model, key: "other:provider", name: "다른 모델" },
];

const nemo: ModelChoice = {
  ...model,
  key: "nemo:provider",
  name: "Mistral Nemo",
};
const supporting: ModelChoice = {
  ...model,
  key: "other:provider",
  name: "다른 모델",
  supportedParameters: ["temperature"],
};
const scenario: ScenarioChoice = {
  key: "1",
  name: "요약",
  prompt: "작업",
  imageRequired: false,
  schemaText: "",
  defaults: { temperature: 0.7 },
};
const scenarioDraft = (commonEnabled: boolean) =>
  simulatorFormSchema.parse({
    ...createDefaultValues(),
    mode: "scenario",
    scenarioKey: scenario.key,
    prompt: "작업",
    commonEnabled,
    comparisons: createComparisons([nemo.key, supporting.key]),
  });

test("모델 이름으로 이미지·파라미터 지원을 추측하지 않는다", () => {
  const values = draft();
  values.files = [new File(["image"], "image.png", { type: "image/png" })];
  values.comparisons[0].settings = {
    mode: "custom",
    temperature: 0,
    maxTokens: 512,
    reasoningEffort: undefined,
  };
  values.jsonSchema = "{}";
  const issues = selectionIssues(values, choices(), []);
  expect(issues).toContain("테스트 모델은 이미지 입력을 지원하지 않습니다.");
  expect(issues).toContain(
    "테스트 모델은 Temperature 지정을 지원하지 않습니다.",
  );
  expect(issues).toContain(
    "테스트 모델은 최대 출력 토큰 지정을 지원하지 않습니다.",
  );
  expect(issues).toContain(
    "테스트 모델은 구조화 출력 설정을 지원하지 않습니다.",
  );
});

test("시나리오 기본 Temperature를 받지 못하는 모델은 공통 켬·끔 모두 막지 않는다", () => {
  for (const commonEnabled of [true, false])
    expect(
      selectionIssues(
        scenarioDraft(commonEnabled),
        [nemo, supporting],
        [scenario],
      ),
    ).toEqual([]);
});

test("받지 못하는 모델의 모델별 설정에 직접 넣은 Temperature는 막는다", () => {
  const values = scenarioDraft(false);
  values.comparisons[0].settings = {
    mode: "custom",
    temperature: 0.7,
    maxTokens: undefined,
    reasoningEffort: undefined,
  };
  expect(selectionIssues(values, [nemo, supporting], [scenario])).toContain(
    "Mistral Nemo은 Temperature 지정을 지원하지 않습니다.",
  );
});

test("받지 못해 빠지는 항목을 뺀 값으로 같은 요청 설정인지 비교한다", () => {
  const values = simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    commonEnabled: true,
    temperature: "0.5",
    comparisons: createComparisons([nemo.key, nemo.key]),
  });
  const issues = selectionIssues(values, [nemo], []).join(" ");
  expect(issues).toContain("동일한 요청 설정");
  expect(issues).not.toContain("지원하지 않습니다");
});

// 확인창과 실행 전 검사가 같은 값을 쓰도록, 칸마다 서버가 실제로 보낼 설정을 계산한다.
test("공통 끔이면 시나리오 기본값을 실제 적용 설정에 넣지 않는다", () => {
  const values = scenarioDraft(false);
  expect(
    values.comparisons.map((comparison) =>
      appliedSettings(comparison, values, supporting, scenario),
    ),
  ).toEqual([{}, {}]);
});

test("공통 켬이면 받지 못하는 모델에서만 물려받은 값을 뺀다", () => {
  const values = scenarioDraft(true);
  const [first, second] = values.comparisons;
  expect(appliedSettings(first, values, nemo, scenario)).toEqual({});
  expect(appliedSettings(second, values, supporting, scenario)).toEqual({
    temperature: 0.7,
  });
});

test("허용 목록에 없는 공통 effort는 빼고, 직접 고른 값은 그대로 둔다", () => {
  const lowOnly: ModelChoice = {
    ...model,
    supportedParameters: ["reasoning"],
    tuningParameters: [
      {
        key: "reasoningEffort",
        kind: "choice",
        options: [{ value: "low", label: "낮음" }],
      },
    ],
  };
  const values = simulatorFormSchema.parse({
    ...createDefaultValues(),
    prompt: "작업",
    commonEnabled: true,
    reasoningEffort: "high",
    comparisons: createComparisons([model.key, "other:provider"]),
  });
  expect(appliedSettings(values.comparisons[0], values, lowOnly)).toEqual({});
  values.comparisons[0].settings = {
    mode: "custom",
    temperature: undefined,
    maxTokens: undefined,
    reasoningEffort: "high",
  };
  expect(appliedSettings(values.comparisons[0], values, lowOnly)).toEqual({
    reasoningEffort: "high",
  });
});

test("비활성·사라진 모델과 시나리오를 실행 전에 차단한다", () => {
  expect(
    selectionIssues(draft(), [{ ...model, selectable: false }], []),
  ).toContain(
    "선택할 수 없는 모델이 있습니다. 모델을 다시 선택하시기 바랍니다.",
  );
  expect(
    selectionIssues(
      { ...draft(), mode: "scenario", scenarioKey: "gone" },
      choices(),
      [],
    ),
  ).toContain("시나리오를 다시 선택하시기 바랍니다.");
});

test("기본 설정은 지원하지 않는 파라미터를 명시적으로 전달하지 않는다", () => {
  expect(selectionIssues(draft(), choices(), [])).toEqual([]);
});

test("칸 설정 상태 이름은 공통 설정 사용 여부에 따라 달라진다", () => {
  expect(comparisonModeLabel("custom", false)).toBe("개별 지정");
  expect(comparisonModeLabel("shared", true)).toBe("공통 설정");
  expect(comparisonModeLabel("shared", false)).toBe("기본값");
});

test("공통 설정 안내는 잠김, 끔, 켬을 구분한다", () => {
  expect(commonSettingsNote(false, true)).toContain("모델별 설정을 해제하면");
  expect(commonSettingsNote(false, false)).toContain(
    "시나리오 기본값을 쓰지 않아요",
  );
  expect(commonSettingsNote(true, false)).toContain("그 항목만 빼고");
});

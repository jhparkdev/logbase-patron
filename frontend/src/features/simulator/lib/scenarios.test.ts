import { expect, test } from "vitest";
import { SCENARIO } from "../../../test/simulationHistoryApi";
import { restorableScenarios, toScenarioChoice } from "./scenarios";

test("시나리오를 폼 선택지로 바꾼다", () => {
  expect(
    toScenarioChoice({
      ...SCENARIO,
      default_json_schema: { type: "object" },
      default_execution_config: {
        temperature: 0.3,
        max_tokens: 512,
        reasoning_effort: "low",
      },
    }),
  ).toEqual({
    key: "3",
    name: "데이터 요약",
    prompt: "다음 데이터를 요약하세요.",
    imageRequired: false,
    schemaText: JSON.stringify({ type: "object" }, null, 2),
    defaults: { temperature: 0.3, maxTokens: 512, reasoningEffort: "low" },
  });
});

test.each([
  ["TEXT", false],
  ["IMAGE", true],
  ["TEXT_IMAGE", true],
] as const)(
  "입력 유형 %s의 이미지 필요 여부는 %s다",
  (input_type, required) => {
    expect(toScenarioChoice({ ...SCENARIO, input_type }).imageRequired).toBe(
      required,
    );
  },
);

test("기본값이 없거나 형식이 다른 설정은 비워 둔다", () => {
  const empty = toScenarioChoice({
    ...SCENARIO,
    default_json_schema: null,
    default_execution_config: { temperature: "0.3", max_tokens: null },
  });
  expect(empty.schemaText).toBe("");
  expect(empty.defaults).toEqual({});
});

const INACTIVE = { ...SCENARIO, scenario_id: 9, is_active: false };
const OTHER_INACTIVE = { ...SCENARIO, scenario_id: 10, is_active: false };

test("재실행 선택지는 활성 시나리오와 원본 시나리오만 남긴다", () => {
  const keys = (sourceId: number | null) =>
    restorableScenarios([SCENARIO, INACTIVE, OTHER_INACTIVE], sourceId).map(
      (item) => item.key,
    );
  expect(keys(9)).toEqual(["3", "9"]);
  expect(keys(3)).toEqual(["3"]);
  expect(keys(null)).toEqual(["3"]);
});

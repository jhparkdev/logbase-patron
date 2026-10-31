import { expect, test } from "vitest";
import { commonEffortOptions } from "./common-parameters";
import type { ModelChoice } from "./presentation";

const choice: ModelChoice = {
  key: "a:p",
  name: "모델 A",
  provider: "p",
  selectable: true,
  supportsImages: false,
  supportedParameters: ["reasoning"],
};
const parameter = (values: string[]) => ({
  key: "reasoningEffort" as const,
  kind: "choice" as const,
  options: values.map((value) => ({ value, label: value })),
});

test("공통 effort는 활성 카탈로그의 확인된 선택지만 중복 없이 모은다", () => {
  expect(
    commonEffortOptions([
      { ...choice, tuningParameters: [parameter(["low", "high"])] },
      {
        ...choice,
        key: "b:p",
        tuningParameters: [parameter(["high", "medium"])],
      },
      {
        ...choice,
        key: "c:p",
        selectable: false,
        tuningParameters: [parameter(["disabled-model-only"])],
      },
    ]).map((option) => option.value),
  ).toEqual(["low", "high", "medium"]);
  expect(commonEffortOptions([choice])).toEqual([]);
  expect(commonEffortOptions([])).toEqual([]);
});

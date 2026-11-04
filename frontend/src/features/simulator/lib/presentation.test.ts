import { expect, test } from "vitest";
import { createComparisons } from "./comparisons";
import { createDefaultValues, simulatorFormSchema } from "./form";
import { type ModelChoice, selectionIssues } from "./presentation";

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

test("모델 이름으로 이미지·파라미터 지원을 추측하지 않는다", () => {
  const values = draft();
  values.files = [new File(["image"], "image.png", { type: "image/png" })];
  values.temperature = 0;
  values.maxTokens = 512;
  values.jsonSchema = "{}";
  const issues = selectionIssues(values, choices(), []);
  expect(issues).toContain("테스트 모델은 이미지 입력을 지원하지 않아요.");
  expect(issues).toContain("테스트 모델은 Temperature 지정을 지원하지 않아요.");
  expect(issues).toContain(
    "테스트 모델은 최대 출력 토큰 지정을 지원하지 않아요.",
  );
  expect(issues).toContain("테스트 모델은 구조화 출력 설정을 지원하지 않아요.");
});

test("비활성·사라진 모델과 시나리오를 실행 전에 차단한다", () => {
  expect(
    selectionIssues(draft(), [{ ...model, selectable: false }], []),
  ).toContain("고를 수 없는 모델이 있어요. 모델을 다시 골라 주세요.");
  expect(
    selectionIssues(
      { ...draft(), mode: "scenario", scenarioKey: "gone" },
      choices(),
      [],
    ),
  ).toContain("시나리오를 다시 골라 주세요.");
});

test("기본 설정은 지원하지 않는 파라미터를 명시적으로 전달하지 않는다", () => {
  expect(selectionIssues(draft(), choices(), [])).toEqual([]);
});

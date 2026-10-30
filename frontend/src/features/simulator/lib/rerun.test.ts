import { expect, test } from "vitest";
import { createDefaultValues } from "./form";
import type { ModelChoice } from "./presentation";
import { restoreRerunValues } from "./rerun";

const choices: ModelChoice[] = [
  {
    key: "a:p",
    name: "모델 A",
    provider: "p",
    selectable: true,
    supportsImages: true,
    supportedParameters: [],
  },
  {
    key: "b:p",
    name: "모델 B",
    provider: "p",
    selectable: false,
    supportsImages: false,
    supportedParameters: [],
  },
];
test("과거 원문과 설정을 보존하고 비활성·누락 모델 자리를 비워 교체하도록 한다", () => {
  const source = createDefaultValues({
    prompt: "과거 Prompt",
    text: "원문",
    temperature: "0.3",
    maxTokens: "512",
    jsonSchema: "{}",
    selections: ["a:p", "b:p", "deleted:p"],
  });
  const before = structuredClone(source);
  const restored = restoreRerunValues(source, choices, []);
  expect(restored.values).toMatchObject({
    prompt: "과거 Prompt",
    text: "원문",
    temperature: "0.3",
    maxTokens: "512",
    jsonSchema: "{}",
    selections: ["a:p", "", ""],
  });
  expect(restored.warnings.join(" ")).toContain("교체");
  expect(restored.warnings.join(" ")).toContain("2개");
  expect(source).toEqual(before);
});
test("삭제된 시나리오는 저장된 원문을 유지하며 Custom으로 전환한다", () => {
  const restored = restoreRerunValues(
    createDefaultValues({
      mode: "scenario",
      scenarioKey: "old",
      prompt: "이전 템플릿 원문",
      selections: ["a:p", "a:q"],
    }),
    choices,
    [],
  );
  expect(restored.values).toMatchObject({
    mode: "custom",
    scenarioKey: "",
    prompt: "이전 템플릿 원문",
  });
  expect(restored.warnings.join(" ")).toContain("Custom");
});

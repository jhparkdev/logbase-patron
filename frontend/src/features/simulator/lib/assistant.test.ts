import { expect, test } from "vitest";
import {
  applyAssistantPatch,
  assistantPatchIssue,
  simulatorAssistantState,
  simulatorRevision,
} from "./assistant";
import { createComparison } from "./comparisons";
import { createDefaultValues } from "./form";

test("a partial change keeps prompt, input, uploads and other settings", () => {
  const current = createDefaultValues({
    prompt: "keep",
    text: "input",
    commonEnabled: true,
    temperature: "0.3",
    existingAssetIds: ["asset"],
  });
  const next = applyAssistantPatch(current, {
    execution_config: { max_tokens: 2048 },
  });
  expect(next.prompt).toBe("keep");
  expect(next.text).toBe("input");
  expect(next.temperature).toBe("0.3");
  expect(next.maxTokens).toBe("2048");
  expect(next.commonEnabled).toBe(true);
  expect(next.existingAssetIds).toEqual(["asset"]);
  expect(current.maxTokens).toBe("");
});

test("explicit null clears while an omitted field stays untouched", () => {
  const current = createDefaultValues({ temperature: "0.3", maxTokens: "512" });
  const next = applyAssistantPatch(current, {
    execution_config: { max_tokens: null },
  });
  expect(next.maxTokens).toBe("");
  expect(next.temperature).toBe("0.3");
  // 값을 지우기만 하는 요청은 꺼진 공통 설정을 켜지 않는다.
  expect(next.commonEnabled).toBe(false);
});

test("setting a common value turns common settings on so the run uses it", () => {
  const current = createDefaultValues({ commonEnabled: false });
  const next = applyAssistantPatch(current, {
    execution_config: { max_tokens: 2048 },
  });
  expect(next.commonEnabled).toBe(true);
  expect(next.maxTokens).toBe("2048");
});

test("turning common settings on does not revive values left while it was off", () => {
  const current = createDefaultValues({
    commonEnabled: false,
    temperature: "0.3",
    maxTokens: "512",
    reasoningEffort: "high",
  });
  const next = applyAssistantPatch(current, {
    execution_config: { max_tokens: 2048 },
  });
  expect(next.commonEnabled).toBe(true);
  expect(next.maxTokens).toBe("2048");
  expect(next.temperature).toBe("");
  expect(next.reasoningEffort).toBe("");
});

test("per-model settings from the assistant turn common settings off like the screen does", () => {
  const current = createDefaultValues({
    commonEnabled: true,
    maxTokens: "512",
  });
  const next = applyAssistantPatch(current, {
    models: [
      {
        model_id: 1,
        execution_provider: "A",
        execution_config: { temperature: 0.2 },
      },
      { model_id: 2, execution_provider: "B", execution_config: {} },
    ],
  });
  expect(next.comparisons[0].settings.mode).toBe("custom");
  expect(next.commonEnabled).toBe(false);
});

test("a common value is not applied while a comparison uses per-model settings", () => {
  const custom = createComparison("1:A");
  custom.settings.mode = "custom";
  const current = createDefaultValues({ comparisons: [custom] });
  const next = applyAssistantPatch(current, {
    execution_config: { max_tokens: 2048 },
  });
  expect(assistantPatchIssue(next, [], [])).toContain("모델별 설정");
});

test("the assistant sees common values only while common settings are on", () => {
  const off = createDefaultValues({ commonEnabled: false, maxTokens: "512" });
  const on = { ...off, commonEnabled: true };
  expect(simulatorAssistantState(off).execution_config).toEqual({});
  expect(simulatorAssistantState(on).execution_config?.max_tokens).toBe(512);
});

test("a user's edit changes the revision used to reject late responses", () => {
  const current = createDefaultValues({ prompt: "first" });
  expect(simulatorRevision(current)).not.toBe(
    simulatorRevision({ ...current, prompt: "edited" }),
  );
});

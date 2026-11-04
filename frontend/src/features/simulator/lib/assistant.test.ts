import { expect, test } from "vitest";
import { applyAssistantPatch, simulatorRevision } from "./assistant";
import { createDefaultValues } from "./form";

test("a partial change keeps prompt, input, uploads and other settings", () => {
  const current = createDefaultValues({
    prompt: "keep",
    text: "input",
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
});

test("a user's edit changes the revision used to reject late responses", () => {
  const current = createDefaultValues({ prompt: "first" });
  expect(simulatorRevision(current)).not.toBe(
    simulatorRevision({ ...current, prompt: "edited" }),
  );
});

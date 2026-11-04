import { expect, test } from "vitest";
import { createAssistantBridge } from "./assistant";

test("leaving P04 unregisters its form and an old cleanup cannot remove a new form", () => {
  const bridge = createAssistantBridge();
  const first = {
    read: () => {
      throw new Error();
    },
    apply: () => undefined,
    undo: () => undefined,
  };
  const second = { ...first };
  const cleanup = bridge.register(first);
  bridge.register(second);
  cleanup();
  expect(bridge.getSnapshot()).toBe(second);
});

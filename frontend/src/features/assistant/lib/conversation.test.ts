import { expect, test } from "vitest";
import { type ChatMessage, requestMessages } from "./conversation";

test("request history is bounded and cannot include UI-only patch data", () => {
  const history: ChatMessage[] = Array.from({ length: 20 }, (_, index) => ({
    id: `${index}`,
    role: index % 2 ? "assistant" : "user",
    content: "가".repeat(1000),
    patch: { prompt_text: "private UI action" },
  }));
  const messages = requestMessages(history, "latest");
  expect(messages.length).toBeLessThanOrEqual(12);
  expect(
    messages.reduce((total, message) => total + message.content.length, 0),
  ).toBeLessThanOrEqual(8000);
  expect(messages.at(-1)?.content).toBe("latest");
  expect(messages.every((message) => !("patch" in message))).toBe(true);
});

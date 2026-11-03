import { expect, test } from "vitest";
import { testPromptFormSchema } from "./testForm";

const parse = (prompt: string) => testPromptFormSchema.safeParse({ prompt });

test("앞뒤 공백은 지우고 값을 돌려준다", () => {
  expect(parse("  안녕  ")).toMatchObject({
    success: true,
    data: { prompt: "안녕" },
  });
});

test("Prompt는 비워도 된다", () => {
  expect(parse("").success).toBe(true);
  expect(parse("   ").success).toBe(true);
});

test("Prompt는 1000자까지 받는다", () => {
  expect(parse("a".repeat(1000)).success).toBe(true);
  expect(parse("a".repeat(1001)).success).toBe(false);
});

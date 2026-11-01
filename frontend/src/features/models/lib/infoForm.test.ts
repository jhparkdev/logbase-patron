import { expect, test } from "vitest";
import {
  displayNameFormSchema,
  purposeFormSchema,
  registerFormSchema,
} from "./infoForm";

test("앞뒤 공백은 지우고 값을 돌려준다", () => {
  expect(displayNameFormSchema.safeParse({ value: "  GPT  " })).toMatchObject({
    success: true,
    data: { value: "GPT" },
  });
  expect(purposeFormSchema.safeParse({ value: "  요약  " })).toMatchObject({
    success: true,
    data: { value: "요약" },
  });
});

test("표시 이름은 비우거나 공백만 넣을 수 없다", () => {
  expect(displayNameFormSchema.safeParse({ value: "" }).success).toBe(false);
  expect(displayNameFormSchema.safeParse({ value: "   " }).success).toBe(false);
});

test("표시 이름은 100자까지 받는다", () => {
  const parse = (value: string) =>
    displayNameFormSchema.safeParse({ value }).success;
  expect(parse("a".repeat(100))).toBe(true);
  expect(parse("a".repeat(101))).toBe(false);
});

test("용도는 비워도 되고 200자까지 받는다", () => {
  const parse = (value: string) =>
    purposeFormSchema.safeParse({ value }).success;
  expect(parse("")).toBe(true);
  expect(parse("a".repeat(200))).toBe(true);
  expect(parse("a".repeat(201))).toBe(false);
});

test("등록 폼은 표시 이름과 용도를 각 항목과 같은 규칙으로 검증한다", () => {
  const parse = (displayName: string, purpose: string) =>
    registerFormSchema.safeParse({ displayName, purpose });
  expect(parse("  GPT  ", "  요약  ")).toMatchObject({
    success: true,
    data: { displayName: "GPT", purpose: "요약" },
  });
  expect(parse("", "").success).toBe(false);
  expect(parse("a".repeat(101), "").success).toBe(false);
  expect(parse("GPT", "").success).toBe(true);
  expect(parse("GPT", "a".repeat(201)).success).toBe(false);
});

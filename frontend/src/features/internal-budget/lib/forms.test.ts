import { describe, expect, test } from "vitest";
import type { z } from "zod";
import { budgetFormSchema, subscriptionFormSchema } from "./forms";

/** 칸마다 첫 번째 오류 문구. 오류가 없는 칸은 빠진다. */
function errors(schema: z.ZodType, values: Record<string, unknown>) {
  const result = schema.safeParse(values);
  const messages: Record<string, string> = {};
  for (const issue of result.error?.issues ?? []) {
    messages[String(issue.path[0])] ??= issue.message;
  }
  return messages;
}

describe("budgetFormSchema", () => {
  const valid = { amount: "5000", effectiveFrom: "2026-10" };

  test("0보다 큰 금액과 적용 시작 월이면 통과한다", () => {
    expect(errors(budgetFormSchema, valid)).toEqual({});
    expect(errors(budgetFormSchema, { ...valid, amount: "0.01" })).toEqual({});
  });

  test("금액이 비었거나, 숫자가 아니거나, 0 이하이면 거절한다", () => {
    expect(errors(budgetFormSchema, { ...valid, amount: " " })).toEqual({
      amount: "월 예산을 입력해 주세요.",
    });
    expect(errors(budgetFormSchema, { ...valid, amount: "오천" })).toEqual({
      amount: "숫자로 입력해 주세요.",
    });
    for (const amount of ["0", "0.00", "-10"]) {
      expect(errors(budgetFormSchema, { ...valid, amount })).toEqual({
        amount: "월 예산은 0보다 커야 해요.",
      });
    }
  });

  test("적용 시작 월이 비었거나 달력에 없는 달이면 거절한다", () => {
    for (const effectiveFrom of ["", "2026-13"]) {
      expect(errors(budgetFormSchema, { ...valid, effectiveFrom })).toEqual({
        effectiveFrom: "적용 시작 월을 골라 주세요.",
      });
    }
  });
});

describe("subscriptionFormSchema", () => {
  const valid = {
    toolName: "ChatGPT Team",
    month: "2026-10",
    amount: "600",
    status: "active",
    note: "",
  };

  test("필수 칸을 채우면 통과하고 금액 0도 받는다", () => {
    expect(errors(subscriptionFormSchema, valid)).toEqual({});
    expect(errors(subscriptionFormSchema, { ...valid, amount: "0" })).toEqual(
      {},
    );
  });

  test("도구명·적용 월·금액이 비면 각각 알려 준다", () => {
    expect(
      errors(subscriptionFormSchema, {
        ...valid,
        toolName: " ",
        month: "",
        amount: "",
      }),
    ).toEqual({
      toolName: "도구명을 입력해 주세요.",
      month: "적용 월을 골라 주세요.",
      amount: "금액을 입력해 주세요.",
    });
  });

  test("음수 금액은 거절한다", () => {
    expect(errors(subscriptionFormSchema, { ...valid, amount: "-10" })).toEqual(
      { amount: "금액은 0 이상이어야 해요." },
    );
  });
});

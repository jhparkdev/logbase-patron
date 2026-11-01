import { describe, expect, test } from "vitest";
import { schemaErrors } from "../../test/schemaErrors";
import { budgetFormSchema } from "./budget";

describe("budgetFormSchema", () => {
  const valid = { amount: "5000", effectiveFrom: "2026-10" };

  test("0보다 큰 금액과 적용 시작 월이면 통과한다", () => {
    expect(schemaErrors(budgetFormSchema, valid)).toEqual({});
    expect(
      schemaErrors(budgetFormSchema, { ...valid, amount: "0.01" }),
    ).toEqual({});
  });

  test("금액이 비었거나, 숫자가 아니거나, 0 이하이면 거절한다", () => {
    expect(schemaErrors(budgetFormSchema, { ...valid, amount: " " })).toEqual({
      amount: "월 예산을 입력해 주세요.",
    });
    expect(
      schemaErrors(budgetFormSchema, { ...valid, amount: "오천" }),
    ).toEqual({
      amount: "숫자로 입력해 주세요.",
    });
    for (const amount of ["0", "0.00", "-10"]) {
      expect(schemaErrors(budgetFormSchema, { ...valid, amount })).toEqual({
        amount: "월 예산은 0보다 커야 해요.",
      });
    }
  });

  test("적용 시작 월이 비었거나 달력에 없는 달이면 거절한다", () => {
    for (const effectiveFrom of ["", "2026-13"]) {
      expect(
        schemaErrors(budgetFormSchema, { ...valid, effectiveFrom }),
      ).toEqual({
        effectiveFrom: "적용 시작 월을 골라 주세요.",
      });
    }
  });
});

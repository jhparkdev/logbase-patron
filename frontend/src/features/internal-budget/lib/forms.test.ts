import { describe, expect, test } from "vitest";
import { schemaErrors } from "../../../test/schemaErrors";
import { subscriptionFormSchema } from "./forms";

describe("subscriptionFormSchema", () => {
  const valid = {
    toolName: "ChatGPT Team",
    month: "2026-10",
    amount: "600",
    status: "active",
    note: "",
  };

  test("필수 칸을 채우면 통과하고 금액 0도 받는다", () => {
    expect(schemaErrors(subscriptionFormSchema, valid)).toEqual({});
    expect(
      schemaErrors(subscriptionFormSchema, { ...valid, amount: "0" }),
    ).toEqual({});
  });

  test("도구명·적용 월·금액이 비면 각각 알려 준다", () => {
    expect(
      schemaErrors(subscriptionFormSchema, {
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
    expect(
      schemaErrors(subscriptionFormSchema, { ...valid, amount: "-10" }),
    ).toEqual({ amount: "금액은 0 이상이어야 해요." });
  });
});

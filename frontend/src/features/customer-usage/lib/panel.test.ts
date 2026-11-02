import { describe, expect, test } from "vitest";
import { remainingBudget, serviceBudgetShare } from "./panel";

describe("remainingBudget", () => {
  test("예산이 없으면 남은 예산 줄을 보여 주지 않는다", () => {
    expect(remainingBudget(null)).toBeUndefined();
  });

  test("예산이 남았으면 남은 예산으로 보여 준다", () => {
    expect(remainingBudget("275.80")).toEqual({
      label: "남은 예산",
      amount: "275.80",
      over: false,
    });
  });

  test("예산을 넘었으면 음수 대신 초과 금액으로 보여 준다", () => {
    expect(remainingBudget("-2.10")).toEqual({
      label: "초과 금액",
      amount: "2.10",
      over: true,
    });
  });
});

describe("serviceBudgetShare", () => {
  test("예산이 없으면 0%가 아니라 미설정이다", () => {
    expect(serviceBudgetShare(null)).toEqual({ label: "예산 미설정" });
  });

  test("비중을 정수로 보여 주고 막대 너비도 같은 값을 쓴다", () => {
    expect(serviceBudgetShare("52.30")).toEqual({
      label: "예산의 52%",
      width: 52,
    });
  });

  test("100%를 넘으면 글자는 실제 비중, 막대는 꽉 찬 채로 둔다", () => {
    expect(serviceBudgetShare("121.00")).toEqual({
      label: "예산의 121%",
      width: 100,
    });
  });
});

import { describe, expect, test } from "vitest";
import { schemaErrors } from "../../test/schemaErrors";
import {
  amountForInput,
  budgetFormSchema,
  budgetMonthOf,
  budgetStatusBadge,
  remainingBudget,
  serviceBudgetShare,
  usageView,
} from "./budget";

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

describe("budgetMonthOf", () => {
  test("조회 기간 종료일이 속한 달이다", () => {
    expect(budgetMonthOf({ from: "2026-10-02", to: "2026-10-31" })).toBe(
      "2026-10",
    );
  });

  test("기간이 두 달에 걸치면 종료일의 달이다", () => {
    expect(budgetMonthOf({ from: "2026-09-30", to: "2026-10-01" })).toBe(
      "2026-10",
    );
    expect(budgetMonthOf({ from: "2025-12-31", to: "2026-01-01" })).toBe(
      "2026-01",
    );
  });
});

describe("usageView", () => {
  test("서버의 상태를 그대로 쓰고 사용률은 정수로 보여 준다", () => {
    expect(usageView({ status: "WARNING", usage_pct: "82.60" })).toEqual({
      status: "warning",
      percent: 83,
    });
    expect(usageView({ status: "OVER", usage_pct: "121.00" })).toEqual({
      status: "over",
      percent: 121,
    });
    expect(usageView({ status: "NORMAL", usage_pct: "0.00" })).toEqual({
      status: "normal",
      percent: 0,
    });
  });

  test("예산이 없으면 0%가 아니라 미설정이다", () => {
    expect(usageView({ status: "UNSET", usage_pct: null })).toEqual({
      status: "unset",
    });
  });
});

describe("budgetStatusBadge", () => {
  test.each([
    ["NORMAL", "정상", "green"],
    ["WARNING", "주의", "yellow"],
    ["OVER", "초과", "red"],
    ["UNSET", "미설정", "grey"],
  ] as const)("%s는 %s로 보여 준다", (status, label, tone) => {
    expect(budgetStatusBadge(status)).toEqual({ label, tone });
  });
});

describe("amountForInput", () => {
  test("입력 칸에 넣을 때 뒤쪽 0만 지운다", () => {
    expect(amountForInput("1.970000000000000000")).toBe("1.97");
    expect(amountForInput("90.000000000000000000")).toBe("90");
    expect(amountForInput("100")).toBe("100");
  });

  test("예산이 없으면 빈 칸이다", () => {
    expect(amountForInput(null)).toBe("");
  });
});

describe("remainingBudget", () => {
  test("예산이 없으면 남은 예산 줄을 보여 주지 않는다", () => {
    expect(remainingBudget(null)).toBeUndefined();
  });

  test("예산이 남았으면 남은 예산, 넘었으면 음수 대신 초과 금액으로 보여 준다", () => {
    expect(remainingBudget("275.80")).toEqual({
      label: "남은 예산",
      amount: "275.80",
      over: false,
    });
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

  test("비중은 정수로, 막대는 100%에서 멈춘다", () => {
    expect(serviceBudgetShare("52.30")).toEqual({
      label: "예산의 52%",
      percent: 52,
      width: 52,
    });
    expect(serviceBudgetShare("121.00")).toEqual({
      label: "예산의 121%",
      percent: 121,
      width: 100,
    });
  });
});

import { describe, expect, test } from "vitest";
import { budgetSegments, costBreakdown, usageHeadline } from "./project";

const DETAIL = {
  confirmed_cost_usd: "1850.00",
  estimated_cost_usd: "310.00",
  subscription_usd: "800.00",
  budget: {
    monthly_amount_usd: "4000.00",
    used_usd: "2960.00",
    usage_pct: "74.00",
    status: "NORMAL",
  },
} as const;

describe("budgetSegments", () => {
  test("확정·추정·구독료가 예산에서 차지하는 너비를 서버 금액으로만 구한다", () => {
    expect(budgetSegments(DETAIL)).toEqual([
      { key: "confirmed", width: 46.25 },
      { key: "estimated", width: 7.75 },
      { key: "subscription", width: 20 },
    ]);
  });

  test("예산을 넘으면 앞에서부터 채우고 100%에서 자른다", () => {
    expect(
      budgetSegments({
        ...DETAIL,
        confirmed_cost_usd: "3800.00",
        estimated_cost_usd: "400.00",
        subscription_usd: "800.00",
      }),
    ).toEqual([
      { key: "confirmed", width: 95 },
      { key: "estimated", width: 5 },
      { key: "subscription", width: 0 },
    ]);
  });

  test("예산이 없으면 막대를 그리지 않는다", () => {
    expect(
      budgetSegments({
        ...DETAIL,
        budget: { ...DETAIL.budget, monthly_amount_usd: null },
      }),
    ).toBeUndefined();
  });
});

describe("usageHeadline", () => {
  test("예산이 있으면 사용률, 없으면 미설정이다", () => {
    expect(usageHeadline(DETAIL.budget)).toBe("74% 사용");
    expect(
      usageHeadline({ ...DETAIL.budget, usage_pct: null, status: "UNSET" }),
    ).toBe("예산 미설정");
  });
});

describe("costBreakdown", () => {
  test("사용액을 구성하는 세 금액을 서버 값 그대로, 추정에만 ≈를 붙여 나열한다", () => {
    expect(costBreakdown(DETAIL)).toEqual([
      { key: "confirmed", label: "API 확정 비용", amount: "1,850.00" },
      { key: "estimated", label: "API 추정 비용", amount: "≈ 310.00" },
      { key: "subscription", label: "귀속 구독료", amount: "800.00" },
    ]);
  });

  test("추정이 0이면 ≈를 붙이지 않는다", () => {
    expect(costBreakdown({ ...DETAIL, estimated_cost_usd: "0.00" })[1]).toEqual(
      { key: "estimated", label: "API 추정 비용", amount: "0.00" },
    );
  });
});

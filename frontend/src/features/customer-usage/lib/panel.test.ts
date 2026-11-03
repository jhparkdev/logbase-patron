import { describe, expect, test } from "vitest";
import { budgetFormHint, serviceTotal, warningMark } from "./panel";

describe("warningMark", () => {
  test("서버가 준 주의 기준 사용률을 정수로 돌려준다", () => {
    expect(warningMark({ status: "NORMAL", warning_threshold_pct: "80" })).toBe(
      80,
    );
    expect(
      warningMark({ status: "OVER", warning_threshold_pct: "79.50" }),
    ).toBe(80);
  });

  test("예산이 없으면 기준선을 두지 않는다", () => {
    expect(
      warningMark({ status: "UNSET", warning_threshold_pct: "80" }),
    ).toBeUndefined();
  });
});

describe("serviceTotal", () => {
  test("추정이 섞였으면 ≈를 붙이고 추정 포함을 알린다", () => {
    expect(
      serviceTotal({ total_cost_usd: "12.10", estimated_cost_usd: "10.00" }),
    ).toEqual({ label: "≈ 12.10", note: "추정 포함" });
  });

  test("확정만 있으면 금액 그대로다", () => {
    expect(
      serviceTotal({ total_cost_usd: "2.10", estimated_cost_usd: "0.00" }),
    ).toEqual({ label: "2.10", note: undefined });
  });
});

describe("budgetFormHint", () => {
  test("서버가 준 주의 기준을 넣어 안내한다", () => {
    expect(budgetFormHint({ warning_threshold_pct: "80" })).toBe(
      "한 번 정하면 다음 달에도 그대로 적용돼요. 사용률이 80% 이상이면 주의, 100% 이상이면 초과로 표시해요.",
    );
  });
});

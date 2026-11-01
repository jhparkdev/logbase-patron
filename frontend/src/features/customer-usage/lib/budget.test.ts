import { describe, expect, test } from "vitest";
import { budgetMonthOf } from "./budget";

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

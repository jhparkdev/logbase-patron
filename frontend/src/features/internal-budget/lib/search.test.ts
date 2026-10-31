import { describe, expect, test } from "vitest";
import { parseBudgetSearch } from "./search";

const NOW = new Date("2026-10-20T03:00:00Z");
const THIS_MONTH = { from: "2026-10-01", to: "2026-10-20" };

describe("parseBudgetSearch", () => {
  test("주소에 기간이 없으면 KST 이번 달 1일부터 오늘까지다", () => {
    expect(parseBudgetSearch({}, NOW)).toEqual(THIS_MONTH);
  });

  test("올바른 기간은 그대로 쓴다", () => {
    expect(
      parseBudgetSearch({ from: "2026-09-01", to: "2026-09-30" }, NOW),
    ).toEqual({ from: "2026-09-01", to: "2026-09-30" });
  });

  test("형식이 틀리거나, 순서가 바뀌거나, 366일을 넘으면 이번 달로 본다", () => {
    for (const raw of [
      { from: "abc", to: "2026-10-10" },
      { from: "2026-10-01" },
      { from: "2026-10-10", to: "2026-10-01" },
      { from: "2025-01-01", to: "2026-01-02" },
    ]) {
      expect(parseBudgetSearch(raw, NOW)).toEqual(THIS_MONTH);
    }
  });
});

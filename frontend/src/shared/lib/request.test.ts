import { describe, expect, test } from "vitest";
import { costView, executionStatus } from "./request";

describe("costView", () => {
  test("확정·추정은 금액을 그대로 넘긴다", () => {
    expect(costView({ cost_status: "CONFIRMED", cost_usd: "0.0200" })).toEqual({
      kind: "confirmed",
      amount: "0.0200",
    });
    expect(costView({ cost_status: "ESTIMATED", cost_usd: "0.0800" })).toEqual({
      kind: "estimated",
      amount: "0.0800",
    });
  });

  test("미확인은 금액이 없다", () => {
    expect(costView({ cost_status: "UNKNOWN", cost_usd: null })).toEqual({
      kind: "unknown",
      amount: null,
    });
  });
});

describe("executionStatus", () => {
  test.each([
    ["PENDING", "대기", "grey"],
    ["RUNNING", "실행 중", "grey"],
    ["SUCCESS", "성공", "green"],
    ["FAILED", "실패", "red"],
    ["TIMEOUT", "Timeout", "yellow"],
    ["CANCELLED", "취소", "grey"],
  ] as const)("%s는 %s로, %s 색으로 보여 준다", (status, label, tone) => {
    expect(executionStatus(status)).toEqual({ label, tone });
  });
});

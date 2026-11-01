import { describe, expect, test } from "vitest";
import {
  amountForInput,
  budgetStatusBadge,
  costView,
  executionStatus,
  summaryTrend,
  trendDayLabel,
  trendPoint,
  unreflectedText,
  usageView,
} from "./view";

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

describe("executionStatus", () => {
  test.each([
    ["PENDING", "대기"],
    ["RUNNING", "실행 중"],
    ["SUCCESS", "성공"],
    ["FAILED", "실패"],
    ["TIMEOUT", "Timeout"],
    ["CANCELLED", "취소"],
  ] as const)("%s는 %s로 보여 준다", (status, label) => {
    expect(executionStatus(status).label).toBe(label);
  });
});

describe("summaryTrend", () => {
  test("증가와 감소의 방향과 정수 비율을 만든다", () => {
    expect(summaryTrend("12.40")).toEqual({ direction: "up", rate: "12%" });
    expect(summaryTrend("-5.60")).toEqual({ direction: "down", rate: "6%" });
  });

  test("비교할 값이 없거나 변화가 없으면 증감을 보여 주지 않는다", () => {
    expect(summaryTrend(null)).toBeUndefined();
    expect(summaryTrend("0.00")).toBeUndefined();
    expect(summaryTrend("0.40")).toBeUndefined();
  });
});

describe("trendPoint", () => {
  test("그래프에 그릴 때만 금액을 숫자로 바꾸고 원래 문자열도 남긴다", () => {
    expect(
      trendPoint({
        date: "2026-10-02",
        task_count: 3,
        call_count: 9,
        confirmed_cost_usd: "1.50",
        estimated_cost_usd: "0.25",
        unknown_cost_count: 1,
      }),
    ).toEqual({
      day: "10-02",
      date: "2026-10-02",
      tasks: 3,
      confirmed: 1.5,
      estimated: 0.25,
      confirmedText: "1.50",
      estimatedText: "0.25",
      unknownCount: 1,
    });
  });
});

test("trendDayLabel은 월-일만 보여 준다", () => {
  expect(trendDayLabel("2026-10-02")).toBe("10-02");
});

describe("unreflectedText", () => {
  test("미확인이 있을 때만 문구를 만든다", () => {
    expect(unreflectedText(3)).toBe("미확인 3건 미반영");
    expect(unreflectedText(0)).toBeUndefined();
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

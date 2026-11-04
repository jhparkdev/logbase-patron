import { describe, expect, test } from "vitest";
import { modelName, summaryTrend, trendDayLabel, trendPoint } from "./view";

describe("modelName", () => {
  test("OpenRouter 모델 ID를 제공사와 모델 이름으로 나눈다", () => {
    expect(modelName("openai/gpt-4o")).toEqual({
      provider: "openai",
      name: "gpt-4o",
    });
  });

  test("제공사가 없는 ID는 이름만 보여 준다", () => {
    expect(modelName("gpt-4o")).toEqual({ name: "gpt-4o" });
  });

  test("이름에 /가 더 있어도 첫 / 앞만 제공사로 본다", () => {
    expect(modelName("meta-llama/llama-3.1/instruct")).toEqual({
      provider: "meta-llama",
      name: "llama-3.1/instruct",
    });
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

import { describe, expect, test } from "vitest";
import { currentMonthPeriod, kstToday, periodSchema } from "./period";

describe("kstToday", () => {
  test("UTC 15시(KST 자정) 바로 전까지는 같은 날이다", () => {
    expect(kstToday(new Date("2026-10-31T14:59:59Z"))).toBe("2026-10-31");
  });

  test("UTC 15시 정각부터 KST 다음 날이다", () => {
    expect(kstToday(new Date("2026-10-31T15:00:00Z"))).toBe("2026-11-01");
    expect(kstToday(new Date("2026-10-31T15:00:01Z"))).toBe("2026-11-01");
  });
});

describe("currentMonthPeriod", () => {
  test("KST 기준 이번 달 1일부터 오늘까지다", () => {
    expect(currentMonthPeriod(new Date("2026-10-31T14:59:59Z"))).toEqual({
      from: "2026-10-01",
      to: "2026-10-31",
    });
  });

  test("KST로 달이 바뀌면 새 달의 1일 하루가 된다", () => {
    expect(currentMonthPeriod(new Date("2026-10-31T15:00:00Z"))).toEqual({
      from: "2026-11-01",
      to: "2026-11-01",
    });
  });
});

describe("periodSchema", () => {
  function errorPaths(from: string, to: string) {
    const result = periodSchema.safeParse({ from, to });
    return result.success ? [] : result.error.issues.map((i) => i.path[0]);
  }

  test("시작일과 종료일을 모두 포함해 366일까지 받는다", () => {
    expect(errorPaths("2025-01-01", "2025-12-31")).toEqual([]); // 365일
    expect(errorPaths("2025-01-01", "2026-01-01")).toEqual([]); // 366일
    expect(errorPaths("2025-01-01", "2026-01-02")).toEqual(["to"]); // 367일
  });

  test("윤년이 낀 기간도 날짜 수로 센다", () => {
    expect(errorPaths("2024-01-01", "2024-12-31")).toEqual([]); // 366일
    expect(errorPaths("2024-01-01", "2025-01-01")).toEqual(["to"]); // 367일
  });

  test("하루짜리 기간은 받고, 시작일이 종료일보다 늦으면 거절한다", () => {
    expect(errorPaths("2026-10-30", "2026-10-30")).toEqual([]);
    expect(errorPaths("2026-10-31", "2026-10-30")).toEqual(["from"]);
  });

  test("비었거나 달력에 없는 날짜는 거절한다", () => {
    expect(errorPaths("", "2026-10-30")).toEqual(["from"]);
    expect(errorPaths("2026-02-01", "2026-02-30")).toEqual(["to"]);
  });

  test("366일을 넘으면 줄여 달라고 안내한다", () => {
    const result = periodSchema.safeParse({
      from: "2025-01-01",
      to: "2026-01-02",
    });
    expect(result.error?.issues[0].message).toBe(
      "기간은 최대 366일까지 조회할 수 있어요. 기간을 줄여 주세요.",
    );
  });
});

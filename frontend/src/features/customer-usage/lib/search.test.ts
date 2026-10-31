import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { customerUsageSearchSchema } from "./search";

const RECENT_30_DAYS = { from: "2026-10-02", to: "2026-10-31" };
const PERIOD = { from: "2026-10-01", to: "2026-10-20" };

function parse(raw: Record<string, unknown>) {
  return customerUsageSearchSchema.parse(raw);
}

beforeEach(() => vi.useFakeTimers({ now: new Date("2026-10-31T03:00:00Z") }));
afterEach(() => vi.useRealTimers());

describe("customerUsageSearchSchema 기간", () => {
  test("주소에 기간이 없으면 KST 오늘을 포함한 최근 30일이다", () => {
    expect(parse({})).toEqual(RECENT_30_DAYS);
  });

  test("올바른 기간은 그대로 쓴다", () => {
    expect(parse(PERIOD)).toEqual(PERIOD);
  });

  test("366일까지 받고, 367일부터는 최근 30일로 본다", () => {
    expect(parse({ from: "2025-01-01", to: "2025-12-31" })).toEqual({
      from: "2025-01-01",
      to: "2025-12-31",
    }); // 365일
    expect(parse({ from: "2025-01-01", to: "2026-01-01" })).toEqual({
      from: "2025-01-01",
      to: "2026-01-01",
    }); // 366일
    expect(parse({ from: "2025-01-01", to: "2026-01-02" })).toEqual(
      RECENT_30_DAYS,
    ); // 367일
  });

  test("형식이 틀리거나, 한쪽만 있거나, 순서가 바뀌면 최근 30일로 본다", () => {
    for (const raw of [
      { from: "abc", to: "2026-10-10" },
      { from: 20261001, to: "2026-10-10" },
      { from: "2026-10-01" },
      { from: "2026-10-10", to: "2026-10-01" },
    ]) {
      expect(parse(raw)).toEqual(RECENT_30_DAYS);
    }
  });

  test("기본 기간은 주소를 읽을 때의 시각으로 정한다", () => {
    vi.setSystemTime(new Date("2026-10-31T14:59:59Z"));
    expect(parse({})).toEqual(RECENT_30_DAYS);

    vi.setSystemTime(new Date("2026-10-31T15:00:00Z")); // KST 자정
    expect(parse({})).toEqual({ from: "2026-10-03", to: "2026-11-01" });
  });
});

describe("customerUsageSearchSchema 전체보기", () => {
  test("고객·호출 전체 목록을 받는다", () => {
    for (const view of ["customers", "requests"]) {
      expect(parse({ ...PERIOD, view })).toEqual({ ...PERIOD, view });
    }
  });

  test("전체보기에서도 상세 패널 값을 받는다", () => {
    expect(parse({ ...PERIOD, view: "customers", detail: 3 })).toEqual({
      ...PERIOD,
      view: "customers",
      detail: 3,
    });
  });

  test("없는 목록 이름은 버린다", () => {
    for (const view of ["projects", 1]) {
      expect(parse({ ...PERIOD, view })).toEqual(PERIOD);
    }
  });
});

describe("customerUsageSearchSchema 상세 패널", () => {
  test("상세 패널을 연 고객 번호는 1 이상의 정수만 받는다", () => {
    expect(parse({ ...PERIOD, detail: 3 })).toEqual({ ...PERIOD, detail: 3 });
    for (const detail of [0, -1, 1.5, "abc"]) {
      expect(parse({ ...PERIOD, detail })).toEqual(PERIOD);
    }
  });
});

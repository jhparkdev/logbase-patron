import { describe, expect, test } from "vitest";
import { internalFilterQuery, parseBudgetSearch } from "./search";

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

describe("parseBudgetSearch 정렬·전체 목록", () => {
  const PERIOD = { from: "2026-10-01", to: "2026-10-20" };

  test("표마다 정렬을 따로 받고, 요약 화면에서도 받는다", () => {
    const sorts = {
      projectsSort: "budget",
      projectsOrder: "desc",
      requestsSort: "cost",
      requestsOrder: "asc",
    };
    expect(parseBudgetSearch({ ...PERIOD, ...sorts }, NOW)).toEqual({
      ...PERIOD,
      ...sorts,
    });
  });

  test("그 표에 없는 정렬 칸이나 방향 없는 정렬은 버린다", () => {
    for (const raw of [
      { projectsSort: "tokens", projectsOrder: "asc" },
      { requestsSort: "cost" },
      { subscriptionsSort: "tool", subscriptionsOrder: "sideways" },
    ]) {
      expect(parseBudgetSearch({ ...PERIOD, ...raw }, NOW)).toEqual(PERIOD);
    }
  });

  test("전체 목록과 페이지를 받고, 1 미만이거나 정수가 아닌 페이지는 버린다", () => {
    expect(
      parseBudgetSearch({ ...PERIOD, view: "requests", page: 2 }, NOW),
    ).toEqual({ ...PERIOD, view: "requests", page: 2 });
    for (const page of [0, 1.5]) {
      expect(
        parseBudgetSearch({ ...PERIOD, view: "projects", page }, NOW),
      ).toEqual({ ...PERIOD, view: "projects" });
    }
  });

  test("페이지는 전체 목록에서만 쓰고, 없는 목록 이름은 버린다", () => {
    for (const view of [undefined, "members", "password"]) {
      expect(parseBudgetSearch({ ...PERIOD, view, page: 2 }, NOW)).toEqual(
        PERIOD,
      );
    }
  });
});

describe("parseBudgetSearch 상세 패널", () => {
  const PERIOD = { from: "2026-10-01", to: "2026-10-20" };

  test("프로젝트 번호는 1 이상의 정수만, 구독료는 new만 받는다", () => {
    expect(
      parseBudgetSearch({ ...PERIOD, project: 3, subscription: "new" }, NOW),
    ).toEqual({ ...PERIOD, project: 3, subscription: "new" });
    for (const project of [0, -1, 1.5, "abc"]) {
      expect(parseBudgetSearch({ ...PERIOD, project }, NOW)).toEqual(PERIOD);
    }
    expect(parseBudgetSearch({ ...PERIOD, subscription: 7 }, NOW)).toEqual(
      PERIOD,
    );
  });

  test("전체 목록에서도 패널 값을 받는다", () => {
    expect(
      parseBudgetSearch({ ...PERIOD, view: "projects", project: 3 }, NOW),
    ).toEqual({ ...PERIOD, view: "projects", project: 3 });
  });
});

describe("internalFilterQuery", () => {
  test("주소의 기간을 API 조회 조건 이름으로 바꾼다", () => {
    expect(
      internalFilterQuery({ from: "2026-10-01", to: "2026-10-31" }),
    ).toEqual({ start_date: "2026-10-01", end_date: "2026-10-31" });
  });
});

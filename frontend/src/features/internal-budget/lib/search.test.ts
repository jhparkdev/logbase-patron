import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  budgetSearchSchema,
  internalFilterQuery,
  listSortOf,
  projectRowsQuery,
  requestRowsQuery,
  subscriptionRowsQuery,
} from "./search";

const THIS_MONTH = { from: "2026-10-01", to: "2026-10-20" };
const PERIOD = { from: "2026-10-01", to: "2026-10-20" };

function parse(raw: Record<string, unknown>) {
  return budgetSearchSchema.parse(raw);
}

beforeEach(() => vi.useFakeTimers({ now: new Date("2026-10-20T03:00:00Z") }));
afterEach(() => vi.useRealTimers());

describe("budgetSearchSchema 기간", () => {
  test("주소에 기간이 없으면 KST 이번 달 1일부터 오늘까지다", () => {
    expect(parse({})).toEqual(THIS_MONTH);
  });

  test("이번 달은 KST 달력으로 정한다", () => {
    vi.setSystemTime(new Date("2026-10-31T14:59:59Z"));
    expect(parse({})).toEqual({ from: "2026-10-01", to: "2026-10-31" });

    vi.setSystemTime(new Date("2026-10-31T15:00:00Z")); // KST 11월 1일 0시
    expect(parse({})).toEqual({ from: "2026-11-01", to: "2026-11-01" });
  });

  test("올바른 기간은 그대로 쓴다", () => {
    expect(parse({ from: "2026-09-01", to: "2026-09-30" })).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
    });
  });

  test("형식이 틀리거나, 순서가 바뀌거나, 366일을 넘으면 이번 달로 본다", () => {
    for (const raw of [
      { from: "abc", to: "2026-10-10" },
      { from: "2026-10-01" },
      { from: "2026-10-10", to: "2026-10-01" },
      { from: "2025-01-01", to: "2026-01-02" },
      { from: 20261001, to: 20261010 },
    ]) {
      expect(parse(raw)).toEqual(THIS_MONTH);
    }
  });
});

describe("budgetSearchSchema 정렬·전체 목록", () => {
  test("표마다 정렬을 따로 받고, 요약 화면에서도 받는다", () => {
    const sorts = {
      projectsSort: "budget",
      projectsOrder: "desc",
      subscriptionsSort: "amount",
      subscriptionsOrder: "desc",
      requestsSort: "origin",
      requestsOrder: "asc",
    };
    expect(parse({ ...PERIOD, ...sorts })).toEqual({ ...PERIOD, ...sorts });
  });

  test("그 표에 없는 정렬 칸이나 방향은 버린다", () => {
    expect(
      parse({ ...PERIOD, projectsSort: "tokens", requestsOrder: "sideways" }),
    ).toEqual(PERIOD);
  });

  test("칸과 방향이 함께 있을 때만 정렬로 본다", () => {
    expect(
      listSortOf(parse({ ...PERIOD, requestsSort: "cost" }), "requests"),
    ).toBe(undefined);
    expect(
      listSortOf(
        parse({ ...PERIOD, requestsSort: "cost", requestsOrder: "asc" }),
        "requests",
      ),
    ).toEqual({ key: "cost", direction: "asc" });
  });

  test("전체 목록과 페이지를 받고, 1 미만이거나 정수가 아닌 페이지는 버린다", () => {
    expect(parse({ ...PERIOD, view: "requests", page: 2 })).toEqual({
      ...PERIOD,
      view: "requests",
      page: 2,
    });
    for (const page of [0, 1.5]) {
      expect(parse({ ...PERIOD, view: "projects", page })).toEqual({
        ...PERIOD,
        view: "projects",
      });
    }
  });

  test("페이지는 전체 목록에서만 쓰고, 없는 목록 이름은 버린다", () => {
    for (const view of [undefined, "members", "password"]) {
      expect(parse({ ...PERIOD, view, page: 2 })).toEqual(PERIOD);
    }
  });
});

describe("budgetSearchSchema 상세 패널", () => {
  test("프로젝트 번호는 1 이상의 정수만, 구독료는 new만 받는다", () => {
    expect(parse({ ...PERIOD, project: 3, subscription: "new" })).toEqual({
      ...PERIOD,
      project: 3,
      subscription: "new",
    });
    for (const project of [0, -1, 1.5, "abc"]) {
      expect(parse({ ...PERIOD, project })).toEqual(PERIOD);
    }
    expect(parse({ ...PERIOD, subscription: 7 })).toEqual(PERIOD);
  });

  test("전체 목록에서도 패널 값을 받는다", () => {
    expect(parse({ ...PERIOD, view: "projects", project: 3 })).toEqual({
      ...PERIOD,
      view: "projects",
      project: 3,
    });
  });
});

describe("internalFilterQuery", () => {
  test("주소의 기간을 API 조회 조건 이름으로 바꾼다", () => {
    expect(
      internalFilterQuery({ from: "2026-10-01", to: "2026-10-31" }),
    ).toEqual({ start_date: "2026-10-01", end_date: "2026-10-31" });
  });
});

describe("projectRowsQuery", () => {
  test("요약 화면은 조회 기간 종료일의 달로 미리보기를 요청하고 정렬이 없으면 보내지 않는다", () => {
    expect(
      projectRowsQuery(parse({ from: "2026-09-01", to: "2026-10-15" })),
    ).toEqual({ month: "2026-10", preview: true });
  });

  test("정렬은 칸과 방향이 함께 있을 때만 보낸다", () => {
    expect(
      projectRowsQuery(
        parse({ ...PERIOD, projectsSort: "usage", projectsOrder: "asc" }),
      ),
    ).toEqual({ month: "2026-10", preview: true, sort: "usage", order: "asc" });
    expect(
      projectRowsQuery(parse({ ...PERIOD, projectsSort: "usage" })),
    ).toEqual({ month: "2026-10", preview: true });
  });

  test("전체보기는 페이지를 나눠 요청하고, 다른 목록의 전체보기에서는 미리보기다", () => {
    expect(
      projectRowsQuery(parse({ ...PERIOD, view: "projects", page: 3 })),
    ).toEqual({ month: "2026-10", preview: false, page: 3, page_size: 10 });
    expect(projectRowsQuery(parse({ ...PERIOD, view: "projects" }))).toEqual({
      month: "2026-10",
      preview: false,
      page: 1,
      page_size: 10,
    });
    expect(
      projectRowsQuery(parse({ ...PERIOD, view: "requests", page: 3 })),
    ).toEqual({ month: "2026-10", preview: true });
  });
});

describe("requestRowsQuery", () => {
  test("요약 화면은 조회 기간으로 미리보기를 요청하고 정렬이 없으면 보내지 않는다", () => {
    expect(requestRowsQuery(parse(PERIOD))).toEqual({
      start_date: "2026-10-01",
      end_date: "2026-10-20",
      preview: true,
    });
  });

  test("정렬은 칸과 방향이 함께 있을 때만 보낸다", () => {
    expect(
      requestRowsQuery(
        parse({ ...PERIOD, requestsSort: "cost", requestsOrder: "desc" }),
      ),
    ).toEqual({
      start_date: "2026-10-01",
      end_date: "2026-10-20",
      preview: true,
      sort: "cost",
      order: "desc",
    });
  });

  test("전체보기는 페이지를 나눠 요청한다", () => {
    expect(
      requestRowsQuery(parse({ ...PERIOD, view: "requests", page: 2 })),
    ).toEqual({
      start_date: "2026-10-01",
      end_date: "2026-10-20",
      preview: false,
      page: 2,
      page_size: 10,
    });
  });
});

describe("subscriptionRowsQuery", () => {
  test("요약 화면은 조회 기간으로 미리보기를 요청하고, 정렬을 고르지 않으면 보내지 않는다", () => {
    expect(subscriptionRowsQuery(parse(PERIOD))).toEqual({
      start_date: "2026-10-01",
      end_date: "2026-10-20",
      preview: true,
    });
  });

  test("정렬은 칸과 방향이 함께 있을 때만 보낸다", () => {
    expect(
      subscriptionRowsQuery(
        parse({
          ...PERIOD,
          subscriptionsSort: "amount",
          subscriptionsOrder: "asc",
        }),
      ),
    ).toEqual({
      start_date: "2026-10-01",
      end_date: "2026-10-20",
      preview: true,
      sort: "amount",
      order: "asc",
    });
  });

  test("전체보기는 페이지를 나눠 요청한다", () => {
    expect(
      subscriptionRowsQuery(
        parse({ ...PERIOD, view: "subscriptions", page: 3 }),
      ),
    ).toEqual({
      start_date: "2026-10-01",
      end_date: "2026-10-20",
      preview: false,
      page: 3,
      page_size: 10,
    });
  });
});

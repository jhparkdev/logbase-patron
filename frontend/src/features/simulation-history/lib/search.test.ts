import { expect, test } from "vitest";
import {
  changeHistorySort,
  createHistorySearchSchema,
  historyFiltersSchema,
  recentHistoryFilters,
} from "./search";

const now = new Date("2026-10-29T15:10:00Z");

test.each([
  [undefined, 1],
  [1, 1],
  [2, 2],
  [0, 1],
  [-1, 1],
  [1.5, 1],
  ["abc", 1],
  ["2", 1],
  [Number.MAX_SAFE_INTEGER + 1, 1],
])("URL의 페이지 %s를 %i로 검증한다", (page, expected) => {
  expect(createHistorySearchSchema(now).parse({ page })).toHaveProperty(
    "page",
    expected,
  );
});

test("정렬을 변경하면 필터와 선택은 유지하고 첫 페이지로 돌아간다", () => {
  const search = createHistorySearchSchema(now).parse({
    page: 3,
    status: "FAILED",
    selected: "run-1",
    detail: true,
  });
  expect(changeHistorySort(search, "totalCost")).toMatchObject({
    ...search,
    page: 1,
    sort: "totalCost",
    direction: "asc",
  });
});
test("최근 30일의 기본 기간을 KST 자정 기준으로 계산한다", () => {
  expect(recentHistoryFilters(now)).toMatchObject({
    from: "2026-10-01",
    to: "2026-10-30",
  });
});
test("실재하지 않는 날짜와 역전 기간을 거절한다", () => {
  const base = recentHistoryFilters(now);
  expect(
    historyFiltersSchema.safeParse({ ...base, from: "2026-02-30" }).success,
  ).toBe(false);
  expect(
    historyFiltersSchema.safeParse({ ...base, from: "2026-10-31" }).success,
  ).toBe(false);
});
test.each([
  ["2026-12-30", true],
  ["2026-12-31", true],
  ["2027-01-01", false],
])("조회 기간 366일 경계: %s", (to, valid) => {
  expect(
    historyFiltersSchema.safeParse({
      ...recentHistoryFilters(now),
      from: "2025-12-31",
      to,
    }).success,
  ).toBe(valid);
});
test("잘못된 URL 조건은 안전한 기본값으로 복구하고 알 수 없는 키를 제거한다", () => {
  const search = createHistorySearchSchema(now).parse({
    from: "bad",
    to: "2020-01-01",
    sort: "secret",
    direction: "bad",
    status: "bad",
    detail: "yes",
    prompt: "URL에 남기지 않는다",
  });
  expect(search).toMatchObject({
    ...recentHistoryFilters(now),
    sort: "requestedAt",
    direction: "desc",
    detail: false,
  });
  expect(search).not.toHaveProperty("prompt");
});
test("상세 선택과 검색 조건을 URL에서 함께 복원한다", () => {
  expect(
    createHistorySearchSchema(now).parse({
      ...recentHistoryFilters(now),
      selected: "run-1",
      detail: true,
      sort: "totalCost",
      direction: "asc",
      simulationId: " run-1 ",
    }),
  ).toMatchObject({
    selected: "run-1",
    detail: true,
    simulationId: "run-1",
    sort: "totalCost",
    direction: "asc",
  });
});

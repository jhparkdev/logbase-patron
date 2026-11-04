import { expect, test } from "vitest";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import {
  changeHistorySort,
  createHistorySearchSchema,
  historyFiltersSchema,
  historyListQuery,
  recentHistoryFilters,
} from "./search";

const now = new Date("2026-10-29T15:10:00Z");
const RUN_ID = "01a1611f-3e80-73c5-a130-3efa5a1f75de";

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
    selected: RUN_ID,
    detail: true,
  });
  expect(changeHistorySort(search, "modelCount")).toMatchObject({
    ...search,
    page: 1,
    sort: "modelCount",
    direction: "asc",
  });
});
test("총 비용 정렬은 URL에서 유지하고 서버 조회 조건으로 보낸다", () => {
  const search = createHistorySearchSchema(now).parse({
    sort: "totalCost",
    direction: "desc",
  });
  expect(search).toMatchObject({ sort: "totalCost", direction: "desc" });
  expect(historyListQuery(search)).toMatchObject({
    sort: "totalCost",
    direction: "desc",
  });
});
test("UUID가 아닌 실행 ID는 URL에서 지우고 조회 폼에서는 거절한다", () => {
  const search = createHistorySearchSchema(now).parse({
    simulationId: "run-1",
    selected: "run-1",
    detail: true,
  });
  expect(search).toMatchObject({
    simulationId: "",
    selected: undefined,
    detail: false,
  });
  const base = recentHistoryFilters(now);
  expect(
    historyFiltersSchema.safeParse({ ...base, simulationId: "run-1" }).success,
  ).toBe(false);
  expect(
    historyFiltersSchema.safeParse({ ...base, simulationId: RUN_ID }).success,
  ).toBe(true);
  expect(historyFiltersSchema.safeParse(base).success).toBe(true);
});
test("조회 조건을 API 이름으로 바꾸고 고르지 않은 조건은 보내지 않는다", () => {
  const search = createHistorySearchSchema(now).parse({
    from: "2026-10-01",
    to: "2026-10-30",
    page: 2,
    sort: "status",
    direction: "asc",
  });
  expect(historyListQuery(search)).toEqual({
    start_date: "2026-10-01",
    end_date: "2026-10-30",
    page: 2,
    page_size: PAGE_SIZE,
    sort: "status",
    direction: "asc",
  });
  expect(
    historyListQuery({
      ...search,
      scenario: "3",
      model: "7",
      status: "FAILED",
      simulationId: RUN_ID,
    }),
  ).toMatchObject({
    scenario_id: 3,
    model_id: 7,
    status: "FAILED",
    simulation_id: RUN_ID,
  });
});
test("숫자 ID가 아닌 시나리오·모델 값은 조회 조건으로 보내지 않는다", () => {
  const search = createHistorySearchSchema(now).parse({
    scenario: "abc",
    model: "a:p",
  });
  const query = historyListQuery(search);
  expect(query).not.toHaveProperty("scenario_id");
  expect(query).not.toHaveProperty("model_id");
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
      selected: RUN_ID,
      detail: true,
      sort: "costStatus",
      direction: "asc",
      simulationId: ` ${RUN_ID} `,
    }),
  ).toMatchObject({
    selected: RUN_ID,
    detail: true,
    simulationId: RUN_ID,
    sort: "costStatus",
    direction: "asc",
  });
});

import { expect, test } from "vitest";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import {
  modelListQuery,
  modelSortOf,
  modelSortParams,
  modelsSearchSchema,
} from "./search";

const parse = (input: unknown) => modelsSearchSchema.parse(input);

test("주소의 정렬 값은 백엔드가 허용하는 값만 받는다", () => {
  expect(parse({ sort: "price_input", order: "desc" })).toEqual({
    sort: "price_input",
    order: "desc",
  });
  expect(parse({ sort: "password", order: "sideways" })).toEqual({});
  // 정렬 칸이 아닌 값은 백엔드가 받아도 주소에서는 버림
  expect(parse({ sort: "created_at" })).toEqual({});
});

test("검색어는 비어 있거나 100자를 넘거나 NUL 문자가 있으면 버린다", () => {
  expect(parse({ q: "gpt" })).toEqual({ q: "gpt" });
  expect(parse({ q: "a".repeat(100) }).q).toBe("a".repeat(100));
  expect(parse({ q: "a".repeat(101) }).q).toBeUndefined();
  expect(parse({ q: "" }).q).toBeUndefined();
  expect(parse({ q: "a\u0000b" }).q).toBeUndefined();
});

test("페이지는 1 이상 100000 이하의 정수만 받는다", () => {
  expect(parse({ page: 0 }).page).toBeUndefined();
  expect(parse({ page: 1 }).page).toBe(1);
  expect(parse({ page: 100_000 }).page).toBe(100_000);
  expect(parse({ page: 100_001 }).page).toBeUndefined();
  expect(parse({ page: 1.5 }).page).toBeUndefined();
});

test("정렬 조건은 정렬 값과 방향이 모두 있을 때만 정렬 상태가 된다", () => {
  expect(modelSortOf({ sort: "status", order: "desc" })).toEqual({
    key: "status",
    direction: "desc",
  });
  expect(modelSortOf({ sort: "status" })).toBeUndefined();
  expect(modelSortOf({ order: "asc" })).toBeUndefined();
});

test("조건이 없으면 서버 기본 정렬을 쓰도록 정렬을 보내지 않는다", () => {
  expect(modelListQuery({})).toEqual({
    q: undefined,
    sort: undefined,
    order: undefined,
    page: 1,
    page_size: PAGE_SIZE,
  });
});

test("주소의 조건을 목록 요청 조건으로 바꾼다", () => {
  expect(
    modelListQuery({ q: "gpt", sort: "provider", order: "asc", page: 3 }),
  ).toEqual({
    q: "gpt",
    sort: "provider",
    order: "asc",
    page: 3,
    page_size: PAGE_SIZE,
  });
});

test("정렬을 바꾸면 1페이지로 돌아간다", () => {
  expect(modelSortParams({ key: "status", direction: "asc" })).toEqual({
    sort: "status",
    order: "asc",
    page: undefined,
  });
});

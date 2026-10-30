import { expect, test } from "vitest";
import { nextSort } from "./sort";

test("정렬하지 않은 칸을 누르면 오름차순부터 시작한다", () => {
  expect(nextSort(undefined, "name")).toEqual({
    key: "name",
    direction: "asc",
  });
});

test("같은 칸을 누르면 오름차순과 내림차순을 번갈아 바꾼다", () => {
  expect(nextSort({ key: "name", direction: "asc" }, "name")).toEqual({
    key: "name",
    direction: "desc",
  });
  expect(nextSort({ key: "name", direction: "desc" }, "name")).toEqual({
    key: "name",
    direction: "asc",
  });
});

test("다른 칸을 누르면 그 칸의 오름차순으로 바뀐다", () => {
  expect(nextSort({ key: "name", direction: "desc" }, "status")).toEqual({
    key: "status",
    direction: "asc",
  });
});

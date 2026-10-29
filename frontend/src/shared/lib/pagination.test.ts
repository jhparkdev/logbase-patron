import { describe, expect, test } from "vitest";
import { pageCount, visiblePages } from "./pagination";

describe("pageCount", () => {
  test.each([
    [0, 1],
    [1, 1],
    [10, 1],
    [11, 2],
    [20, 2],
    [21, 3],
  ])("항목 %i개, 페이지당 10개 → %i페이지", (total, expected) => {
    expect(pageCount(total, 10)).toBe(expected);
  });
});

describe("visiblePages", () => {
  test.each([
    [1, 1, [1]],
    [2, 3, [1, 2, 3]],
    [1, 10, [1, 2, 3, 4, 5]],
    [3, 10, [1, 2, 3, 4, 5]],
    [4, 10, [2, 3, 4, 5, 6]],
    [5, 10, [3, 4, 5, 6, 7]],
    [8, 10, [6, 7, 8, 9, 10]],
    [10, 10, [6, 7, 8, 9, 10]],
  ])("현재 %i / 전체 %i → %j", (current, total, expected) => {
    expect(visiblePages(current, total)).toEqual(expected);
  });
});

import { expect, test } from "vitest";
import { DEFAULT_AFTER_LOGIN, safeRedirectTarget } from "./redirectTarget";

test("돌아갈 주소가 없으면 기본 화면으로 간다", () => {
  expect(safeRedirectTarget(undefined)).toBe(DEFAULT_AFTER_LOGIN);
  expect(safeRedirectTarget("")).toBe(DEFAULT_AFTER_LOGIN);
});

test("앱 안의 경로는 조회 조건까지 그대로 돌려준다", () => {
  expect(safeRedirectTarget("/models?sort=status&order=desc&page=2")).toBe(
    "/models?sort=status&order=desc&page=2",
  );
});

test("다른 사이트로 보내는 값은 기본 화면으로 바꾼다", () => {
  for (const value of [
    "https://example.com",
    "//example.com/models",
    "/\\example.com",
    "javascript:alert(1)",
    "models",
  ]) {
    expect(safeRedirectTarget(value)).toBe(DEFAULT_AFTER_LOGIN);
  }
});

test("로그인 화면 자신으로는 돌아가지 않는다", () => {
  expect(safeRedirectTarget("/login")).toBe(DEFAULT_AFTER_LOGIN);
  expect(safeRedirectTarget("/login?redirect=%2Fmodels")).toBe(
    DEFAULT_AFTER_LOGIN,
  );
});

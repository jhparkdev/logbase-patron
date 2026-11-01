import { expect, test } from "vitest";
import { formatPricePerMillion } from "./price";

test("토큰당 단가를 100만 토큰당 단가로 소수점만 옮겨 보여 준다", () => {
  expect(formatPricePerMillion("0.00000015")).toBe("0.15");
  expect(formatPricePerMillion("0.0000025")).toBe("2.50");
  expect(formatPricePerMillion("0.000015")).toBe("15.00");
  expect(formatPricePerMillion("0.000000000001")).toBe("0.000001");
});

test("무료 모델의 0은 0.00으로 보여 준다", () => {
  expect(formatPricePerMillion("0")).toBe("0.00");
  expect(formatPricePerMillion("0.000000000000")).toBe("0.00");
});

test("정수 단가도 옮긴다", () => {
  expect(formatPricePerMillion("1")).toBe("1000000.00");
});

test("금액 형식이 아니면 거절한다", () => {
  for (const value of ["", "abc", "-0.1", "1e-7", "0.1.2"]) {
    expect(() => formatPricePerMillion(value)).toThrow();
  }
});

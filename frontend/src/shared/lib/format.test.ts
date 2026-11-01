import { describe, expect, test } from "vitest";
import {
  formatCount,
  formatKstDateTime,
  formatUsd,
  isZeroAmount,
  unreflectedText,
} from "./format";

describe("formatKstDateTime", () => {
  test.each([
    ["2026-10-28T05:32:21Z", "2026-10-28 14:32:21"],
    // KST 날짜 경계: UTC 15:00이 KST 다음 날 0시
    ["2026-10-28T14:59:59Z", "2026-10-28 23:59:59"],
    ["2026-10-28T15:00:00Z", "2026-10-29 00:00:00"],
    ["2026-10-28T15:00:01Z", "2026-10-29 00:00:01"],
    // 월·연 경계
    ["2026-10-31T15:00:00Z", "2026-11-01 00:00:00"],
    ["2026-12-31T15:00:00Z", "2027-01-01 00:00:00"],
    // 오프셋이 붙은 값과 소수 초
    ["2026-10-28T14:32:21+09:00", "2026-10-28 14:32:21"],
    ["2026-10-28T05:32:21.123456+00:00", "2026-10-28 14:32:21"],
  ])("%s → %s", (utc, kst) => {
    expect(formatKstDateTime(utc)).toBe(kst);
  });

  test("시각으로 읽을 수 없는 값은 거절한다", () => {
    expect(() => formatKstDateTime("어제")).toThrow();
  });
});

describe("formatUsd", () => {
  test.each([
    ["126.5", "summary", "126.50"],
    ["0.02", "perCall", "0.0200"],
    ["0", "summary", "0.00"],
    ["1234567.5", "summary", "1,234,567.50"],
    ["126.500000000000", "summary", "126.50"],
    // 반올림 경계(반올림 자리 숫자 4, 5, 6)
    ["0.12344", "perCall", "0.1234"],
    ["0.12345", "perCall", "0.1235"],
    ["0.12346", "perCall", "0.1235"],
    // 올림이 정수 자리까지 넘어가는 경우
    ["999.995", "summary", "1,000.00"],
    // float로 바꾸면 틀어지는 자릿수도 그대로 다룬다
    ["12345678.123456789012", "perCall", "12,345,678.1235"],
  ] as const)("%s (%s) → %s", (amount, precision, expected) => {
    expect(formatUsd(amount, precision)).toBe(expected);
  });

  test.each(["", "abc", "-1.00", "1e3", "1,000"])(
    "금액 형식이 아닌 값(%s)은 거절한다",
    (amount) => {
      expect(() => formatUsd(amount, "summary")).toThrow();
    },
  );
});

describe("formatCount", () => {
  test.each([
    [0, "0"],
    [98, "98"],
    [1482, "1,482"],
    [24591, "24,591"],
  ])("%i → %s", (count, expected) => {
    expect(formatCount(count)).toBe(expected);
  });
});

describe("isZeroAmount", () => {
  test.each([
    ["0", true],
    ["0.00", true],
    ["0.000000000000", true],
    ["0.000000000001", false],
    ["1", false],
    ["10.00", false],
  ])("%s → %s", (amount, expected) => {
    expect(isZeroAmount(amount)).toBe(expected);
  });
});

describe("unreflectedText", () => {
  test("미확인이 있을 때만 문구를 만든다", () => {
    expect(unreflectedText(3)).toBe("미확인 3건 미반영");
    expect(unreflectedText(0)).toBeUndefined();
  });
});

import { expect, test } from "vitest";
import { formatAssistantProse } from "./assistant-format";

test.each([
  [
    "최근 호출: 2026-11-02T07:11:38.580827Z",
    "최근 호출: 2026년 11월 2일 16:11:38 (한국시간)",
  ],
  ["2026-12-31T15:00:00+00:00", "2027년 1월 1일 00:00:00 (한국시간)"],
  ["2026-11-02T16:11:38+09:00", "2026년 11월 2일 16:11:38 (한국시간)"],
])(
  "ISO dates in prose are displayed in Korean time: %s",
  (source, expected) => {
    expect(formatAssistantProse(source)).toBe(expected);
  },
);

test.each([
  "2026-11-02T07:11:38",
  "2026-02-30T07:11:38Z",
  "2026-13-02T07:11:38Z",
])(
  "invalid dates and dates without a timezone are not guessed: %s",
  (source) => {
    expect(formatAssistantProse(source)).toBe(source);
  },
);

test("counts and USD amounts use existing precision without losing small costs", () => {
  expect(
    formatAssistantProse(
      "12000 토큰 · 2000건 · $1.230000000000 · $0.000000000001",
    ),
  ).toBe("12,000 토큰 · 2,000건 · $1.2300 · $0.000000000001");
  expect(
    formatAssistantProse(
      "미확인 비용 · 0건 · $0 · $1,234.50 · v4.1234 · model-12345",
    ),
  ).toBe("미확인 비용 · 0건 · $0.0000 · $1,234.50 · v4.1234 · model-12345");
});

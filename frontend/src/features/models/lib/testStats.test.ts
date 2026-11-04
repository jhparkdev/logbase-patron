import { expect, test } from "vitest";
import { testStatCells } from "./testStats";

const RESULT = {
  status: "SUCCESS",
  tested_at: "2026-11-01T03:00:00Z",
  latency_ms: 1234,
  input_tokens: 12,
  output_tokens: 30,
  cost_usd: "0.0004",
  cost_status: "CONFIRMED",
  actual_provider: "OpenAI",
  error_type: null,
  error_message: null,
} as const;

test("실행 전에는 네 칸을 빈 표시로 둔다", () => {
  expect(testStatCells(undefined)).toEqual([
    { label: "응답 속도", value: "—" },
    { label: "Input 토큰", value: "—" },
    { label: "Output 토큰", value: "—" },
    { label: "호출 비용", value: "—" },
  ]);
});

test("성공한 결과는 속도를 초로, 토큰 수를 세 자리 구분으로, 비용은 확정·추정 표시로 보여 준다", () => {
  expect(testStatCells(RESULT)).toEqual([
    { label: "응답 속도", value: "1.23", unit: "초" },
    { label: "Input 토큰", value: "12" },
    { label: "Output 토큰", value: "30" },
    { label: "호출 비용", cost: { kind: "confirmed", amount: "0.0004" } },
  ]);
  expect(testStatCells({ ...RESULT, latency_ms: 80 })[0]).toEqual({
    label: "응답 속도",
    value: "0.08",
    unit: "초",
  });
});

test("실패한 결과는 모르는 값을 0이 아니라 미확인으로 보여 준다", () => {
  expect(
    testStatCells({
      ...RESULT,
      status: "FAILED",
      latency_ms: null,
      input_tokens: null,
      output_tokens: null,
      cost_usd: null,
      cost_status: "UNKNOWN",
      actual_provider: null,
    }),
  ).toEqual([
    { label: "응답 속도", value: "미확인" },
    { label: "Input 토큰", value: "미확인" },
    { label: "Output 토큰", value: "미확인" },
    { label: "호출 비용", cost: { kind: "unknown", amount: null } },
  ]);
});

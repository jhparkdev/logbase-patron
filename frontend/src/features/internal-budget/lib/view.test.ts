import { describe, expect, test } from "vitest";
import {
  memberStatusLabel,
  originLabel,
  subscriptionStatusBadge,
} from "./view";

describe("originLabel", () => {
  test.each([
    ["INTERNAL_DEVELOPMENT", "내부 개발"],
    ["SIMULATION", "시뮬레이션"],
    ["SYSTEM_TEST", "연결 테스트"],
    ["CUSTOMER_SERVICE", "고객 사용"],
    ["ASSISTANT", "AI 도우미"],
  ] as const)("%s는 %s로 보여 준다", (origin, label) => {
    expect(originLabel(origin)).toBe(label);
  });
});

describe("subscriptionStatusBadge", () => {
  test("사용 중은 초록, 해지는 회색 배지다", () => {
    expect(subscriptionStatusBadge("ACTIVE")).toEqual({
      label: "사용 중",
      tone: "green",
    });
    expect(subscriptionStatusBadge("CANCELLED")).toEqual({
      label: "해지",
      tone: "grey",
    });
  });
});

describe("memberStatusLabel", () => {
  test.each([
    ["KEY_MISSING", "Key 없음"],
    ["KEY_EXPIRED", "Key 만료"],
    ["KEY_INVALID", "Key 오류"],
    ["FETCH_FAILED", "조회 실패"],
  ] as const)("%s는 %s로 보여 준다", (status, label) => {
    expect(memberStatusLabel(status)).toBe(label);
  });
});

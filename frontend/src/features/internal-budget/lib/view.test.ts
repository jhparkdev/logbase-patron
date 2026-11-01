import { describe, expect, test } from "vitest";
import { originLabel } from "./view";

describe("originLabel", () => {
  test.each([
    ["INTERNAL_DEVELOPMENT", "내부 개발"],
    ["SIMULATION", "시뮬레이션"],
    ["SYSTEM_TEST", "연결 테스트"],
    ["CUSTOMER_SERVICE", "고객 사용"],
  ] as const)("%s는 %s로 보여 준다", (origin, label) => {
    expect(originLabel(origin)).toBe(label);
  });
});

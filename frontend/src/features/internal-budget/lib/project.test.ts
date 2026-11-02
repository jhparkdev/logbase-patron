import { describe, expect, test } from "vitest";
import { projectUsageText } from "./project";

describe("projectUsageText", () => {
  test("사용액과 예산 대비 사용률을 함께 알린다", () => {
    expect(
      projectUsageText({
        used_usd: "3420.500000000000",
        usage_pct: "68.41",
        status: "NORMAL",
      }),
    ).toBe("사용액 3,420.50 USD (추정 포함) · 예산의 68%");
  });

  test("예산이 없으면 0%가 아니라 미설정이다", () => {
    expect(
      projectUsageText({ used_usd: "12", usage_pct: null, status: "UNSET" }),
    ).toBe("사용액 12.00 USD (추정 포함) · 예산 미설정");
  });
});

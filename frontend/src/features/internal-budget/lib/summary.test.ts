import { describe, expect, test } from "vitest";
import { managedTotalCaption } from "./summary";

describe("managedTotalCaption", () => {
  test("미확인 호출이 없으면 합계 구성을 알린다", () => {
    expect(managedTotalCaption(0)).toBe("API 비용 + 구독료");
  });

  test("미확인 호출이 있으면 합계에 넣지 않은 건수를 알린다", () => {
    expect(managedTotalCaption(3)).toBe("미확인 3건 미반영");
  });
});

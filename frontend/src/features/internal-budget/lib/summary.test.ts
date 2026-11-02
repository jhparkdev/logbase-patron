import { describe, expect, test } from "vitest";
import { managedTotalCaption, subscriptionCaption } from "./summary";

describe("managedTotalCaption", () => {
  test("미확인 호출이 없으면 합계 구성을 알린다", () => {
    expect(managedTotalCaption(0, false)).toBe("API 비용 + 구독료");
  });

  test("미확인 호출이 있으면 합계에 넣지 않은 건수를 알린다", () => {
    expect(managedTotalCaption(3, false)).toBe("미확인 3건 미반영");
  });

  test("모델 조건으로 구독료를 뺐으면 API 비용만임을 알린다", () => {
    expect(managedTotalCaption(0, true)).toBe("API 비용만 (구독료 제외)");
  });
});

describe("subscriptionCaption", () => {
  test("모델 조건에서는 구독료를 빼고 보여 준다고 알린다", () => {
    expect(subscriptionCaption(false)).toBe("각 서비스 월 구독료");
    expect(subscriptionCaption(true)).toBe(
      "모델 조건에서는 구독료를 빼고 보여요",
    );
  });
});

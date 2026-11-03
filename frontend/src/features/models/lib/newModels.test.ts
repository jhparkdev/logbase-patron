import { expect, test } from "vitest";
import { newModelsNotice } from "./newModels";

test("새 모델이 없으면 알림을 만들지 않는다", () => {
  expect(newModelsNotice({ days: 30, total: 0 })).toBeNull();
});

test("새 모델 수와 기간만 문구로 만들고 모델 이름은 넣지 않는다", () => {
  expect(newModelsNotice({ days: 30, total: 5 })).toEqual({
    title: "새 모델 5개가 올라왔어요",
    description: "최근 30일 안에 OpenRouter에 올라왔어요.",
  });
});

test("개수는 천 단위로 끊어 보여 준다", () => {
  expect(newModelsNotice({ days: 7, total: 1234 })).toEqual({
    title: "새 모델 1,234개가 올라왔어요",
    description: "최근 7일 안에 OpenRouter에 올라왔어요.",
  });
});

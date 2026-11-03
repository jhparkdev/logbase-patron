import { expect, test } from "vitest";
import { newModelsNotice } from "./newModels";

const names = (...list: string[]) => list.map((name) => ({ name }));

test("새 모델이 없으면 알림을 만들지 않는다", () => {
  expect(newModelsNotice({ days: 30, total: 0, items: [] })).toBeNull();
});

test("새 모델 수와 기간, 가장 최근 모델 이름을 문구로 만든다", () => {
  expect(
    newModelsNotice({ days: 30, total: 2, items: names("A 모델", "B 모델") }),
  ).toEqual({
    title: "새 모델 2개가 올라왔어요",
    description: "최근 30일 안에 올라왔어요. A 모델, B 모델",
  });
});

test("전체가 이름 수보다 많으면 나머지 개수를 '외 N개'로 알린다", () => {
  expect(
    newModelsNotice({
      days: 7,
      total: 1234,
      items: names("A", "B", "C"),
    }),
  ).toEqual({
    title: "새 모델 1,234개가 올라왔어요",
    description: "최근 7일 안에 올라왔어요. A, B, C 외 1,231개",
  });
});

test("서버가 준 이름이 세 개를 넘어도 세 개까지만 보여 준다", () => {
  const notice = newModelsNotice({
    days: 30,
    total: 6,
    items: names("A", "B", "C", "D"),
  });

  expect(notice?.description).toBe("최근 30일 안에 올라왔어요. A, B, C 외 3개");
});

test("이름이 없는데 개수만 있으면 개수만 알린다", () => {
  expect(newModelsNotice({ days: 30, total: 4, items: [] })).toEqual({
    title: "새 모델 4개가 올라왔어요",
    description: "최근 30일 안에 올라왔어요.",
  });
});

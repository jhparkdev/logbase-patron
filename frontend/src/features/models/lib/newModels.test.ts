import { expect, test } from "vitest";
import { hasUnseenNewModels, newModelsNotice } from "./newModels";

test("새 모델이 없으면 알림을 만들지 않는다", () => {
  expect(newModelsNotice({ total: 0 })).toBeNull();
});

test("새로운 모델이 나왔다고 알리고 기간은 문구에 넣지 않는다", () => {
  expect(newModelsNotice({ total: 5 })).toEqual({
    title: "새로운 모델이 나왔어요",
    description: "아직 등록하지 않은 모델 5개가 있어요.",
  });
});

test("개수는 천 단위로 끊어 보여 준다", () => {
  expect(newModelsNotice({ total: 1234 })?.description).toBe(
    "아직 등록하지 않은 모델 1,234개가 있어요.",
  );
});

const LATEST = "2026-11-05T10:00:00Z";

test.each([
  ["새 모델이 없다", null, null, false],
  ["한 번도 확인하지 않았다", LATEST, null, true],
  ["확인한 뒤에 더 새 모델이 나왔다", LATEST, "2026-11-05T09:59:59Z", true],
  ["가장 새 모델까지 확인했다", LATEST, LATEST, false],
  ["확인한 시각이 더 뒤다", LATEST, "2026-11-05T11:00:00Z", false],
  ["확인한 값을 읽을 수 없다", LATEST, "not-a-date", true],
])("%s면 표시는 %s", (_name, latest, seen, expected) => {
  expect(hasUnseenNewModels(latest, seen)).toBe(expected);
});

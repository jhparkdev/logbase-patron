import { expect, test } from "vitest";
import type { CostView, SlotView } from "./presentation";
import { sortSlots } from "./result-sort";

const slot = (
  name: string,
  cost: CostView,
  durationMs: number | null = null,
): SlotView => ({
  key: name,
  name,
  provider: "P",
  status: { label: "성공", tone: "green" },
  durationMs,
  inputTokens: null,
  outputTokens: null,
  cost,
  jsonValidation: "미적용",
  schemaValidation: "미적용",
  response: null,
});
const money = (amount: string): CostView => ({ kind: "confirmed", amount });
const unknown: CostView = { kind: "unknown", amount: null };

test("금액은 숫자로 바꾸지 않고 소수 자릿수가 달라도 정확히 비교한다", () => {
  const slots = [
    slot("A", money("0.000000000011")),
    slot("B", money("0.1")),
    slot("C", money("0.000000000010000")),
  ];
  expect(
    sortSlots(slots, { key: "cost", direction: "asc" }).map((s) => s.key),
  ).toEqual(["C", "A", "B"]);
});

test.each(["asc", "desc"] as const)(
  "비용 미확인은 %s 정렬에서도 0처럼 앞에 오지 않고 맨 뒤다",
  (direction) => {
    const sorted = sortSlots(
      [slot("A", unknown), slot("B", money("0")), slot("C", money("1"))],
      { key: "cost", direction },
    );
    expect(sorted.at(-1)?.key).toBe("A");
  },
);

test.each(["asc", "desc"] as const)(
  "응답 시간이 없는 칸은 %s 정렬에서도 맨 뒤다",
  (direction) => {
    const sorted = sortSlots(
      [slot("A", unknown), slot("B", unknown, 100), slot("C", unknown, 0)],
      { key: "duration", direction },
    );
    expect(sorted.at(-1)?.key).toBe("A");
  },
);

test("이름으로 정렬하고 원본 배열을 바꾸지 않는다", () => {
  const slots = [slot("나", unknown), slot("가", unknown)];
  expect(
    sortSlots(slots, { key: "model", direction: "desc" }).map((s) => s.key),
  ).toEqual(["나", "가"]);
  expect(
    sortSlots(slots, { key: "model", direction: "asc" }).map((s) => s.key),
  ).toEqual(["가", "나"]);
  expect(slots[0].key).toBe("나");
});

import { expect, test } from "vitest";
import type { CostView, SlotView, StatusView } from "./presentation";
import { bestSlotKeys, runProgress } from "./run-progress";

const SUCCESS: StatusView = { label: "성공", tone: "green", ongoing: false };
const TIMEOUT: StatusView = { label: "시간 초과", tone: "yellow" };
const RUNNING: StatusView = { label: "진행 중", tone: "grey", ongoing: true };
const PENDING: StatusView = { label: "대기", tone: "grey", ongoing: true };
const unknown: CostView = { kind: "unknown", amount: null };
const money = (amount: string): CostView => ({ kind: "confirmed", amount });

const slot = (
  key: string,
  status: StatusView,
  durationMs: number | null = null,
  cost: CostView = unknown,
): SlotView => ({
  key,
  name: key,
  provider: "P",
  status,
  durationMs,
  inputTokens: null,
  outputTokens: null,
  cost,
  jsonValidation: "미적용",
  schemaValidation: "미적용",
  response: null,
});

test("끝난 칸 수와 칸별 진행 색을 센다", () => {
  expect(
    runProgress([
      slot("A", SUCCESS),
      slot("B", TIMEOUT),
      slot("C", RUNNING),
      slot("D", PENDING),
    ]),
  ).toEqual({
    total: 4,
    done: 2,
    tones: ["green", "yellow", "brand", "brand"],
  });
});

test("성공한 칸이 둘 이상일 때만 최단·최저를 고른다", () => {
  expect(
    bestSlotKeys([
      slot("A", SUCCESS, 2800, money("0.0073")),
      slot("B", SUCCESS, 3700, money("0.0000294")),
      slot("C", TIMEOUT),
    ]),
  ).toEqual({ fastest: ["A"], cheapest: ["B"] });
  expect(
    bestSlotKeys([
      slot("A", SUCCESS, 2800, money("0.0073")),
      slot("C", TIMEOUT),
    ]),
  ).toEqual({ fastest: [], cheapest: [] });
});

test("같은 값이면 모두 표시하고 금액은 자릿수가 달라도 정확히 비교한다", () => {
  expect(
    bestSlotKeys([
      slot("A", SUCCESS, 100, money("0.1")),
      slot("B", SUCCESS, 100, money("0.10")),
    ]),
  ).toEqual({ fastest: ["A", "B"], cheapest: ["A", "B"] });
});

test("미집계·미확인 칸과 진행 중인 칸은 후보에서 뺀다", () => {
  expect(
    bestSlotKeys([
      slot("A", SUCCESS, null, unknown),
      slot("B", SUCCESS, 100, { kind: "estimated", amount: "0.1" }),
      slot("C", SUCCESS, 200, money("0.2")),
      slot("D", RUNNING, 1, money("0.0001")),
    ]),
  ).toEqual({ fastest: ["B"], cheapest: ["B"] });
});

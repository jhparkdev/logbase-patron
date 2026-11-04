import type { SlotView, StatusView } from "./presentation";
import { compareAmount } from "./result-sort";

export type ProgressTone = StatusView["tone"] | "brand";

/** 진행 띠에 쓰는 값. 끝난 칸은 상태 색, 아직 안 끝난 칸은 brand로 채운다. */
export function runProgress(slots: readonly SlotView[]): {
  total: number;
  done: number;
  tones: ProgressTone[];
} {
  const tones = slots.map<ProgressTone>((slot) =>
    slot.status.ongoing ? "brand" : slot.status.tone,
  );
  return {
    total: slots.length,
    done: slots.filter((slot) => !slot.status.ongoing).length,
    tones,
  };
}

/** 후보가 둘 이상일 때 가장 작은 값을 가진 칸 전부. 합산이 아니라 비교만 한다. */
function minimumKeys<T>(
  candidates: readonly { key: string; value: T }[],
  compare: (a: T, b: T) => number,
): string[] {
  if (candidates.length < 2) return [];
  const best = candidates.reduce((current, item) =>
    compare(item.value, current.value) < 0 ? item : current,
  );
  return candidates
    .filter((item) => compare(item.value, best.value) === 0)
    .map((item) => item.key);
}

/** 성공한 칸 중 가장 빠른 응답과 가장 싼 비용. 미집계·미확인은 0이 아니므로 후보에서 뺀다. */
export function bestSlotKeys(slots: readonly SlotView[]): {
  fastest: string[];
  cheapest: string[];
} {
  const finished = slots.filter(
    (slot) => slot.status.tone === "green" && !slot.status.ongoing,
  );
  return {
    fastest: minimumKeys(
      finished.flatMap((slot) =>
        slot.durationMs === null
          ? []
          : [{ key: slot.key, value: slot.durationMs }],
      ),
      (a, b) => a - b,
    ),
    cheapest: minimumKeys(
      finished.flatMap((slot) =>
        slot.cost.amount === null
          ? []
          : [{ key: slot.key, value: slot.cost.amount }],
      ),
      compareAmount,
    ),
  };
}

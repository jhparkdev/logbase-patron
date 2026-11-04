import type { ResultSort, SlotView } from "./presentation";

type Compare = (a: SlotView, b: SlotView) => number;

/** 금액 문자열을 float으로 바꾸지 않고 자릿수를 맞춰 비교한다. */
export function compareAmount(a: string, b: string): number {
  const [aWhole, aFraction = ""] = a.split(".");
  const [bWhole, bFraction = ""] = b.split(".");
  const width = Math.max(aFraction.length, bFraction.length);
  const left = BigInt(aWhole + aFraction.padEnd(width, "0"));
  const right = BigInt(bWhole + bFraction.padEnd(width, "0"));
  return left < right ? -1 : left > right ? 1 : 0;
}

/** 값이 없는 칸(미확인, 미수신)은 0이 아니므로 방향과 상관없이 맨 뒤에 둔다. */
function compareOptional<T>(
  a: T | null,
  b: T | null,
  direction: number,
  compare: (a: T, b: T) => number,
): number {
  if (a === null || b === null) return a === b ? 0 : a === null ? 1 : -1;
  return compare(a, b) * direction;
}

const byNumber = (a: number, b: number) => a - b;

function comparatorFor(sort: ResultSort): Compare {
  const direction = sort.direction === "asc" ? 1 : -1;
  switch (sort.key) {
    case "model":
      return (a, b) => a.name.localeCompare(b.name) * direction;
    case "duration":
      return (a, b) =>
        compareOptional(a.durationMs, b.durationMs, direction, byNumber);
    case "inputTokens":
      return (a, b) =>
        compareOptional(a.inputTokens, b.inputTokens, direction, byNumber);
    case "outputTokens":
      return (a, b) =>
        compareOptional(a.outputTokens, b.outputTokens, direction, byNumber);
    case "cost":
      return (a, b) =>
        compareOptional(a.cost.amount, b.cost.amount, direction, compareAmount);
  }
}

/** 한 실행의 모델 칸(최대 4개)을 전부 받아 정렬한다. 나눠 받는 목록이 아니라 화면에서 정렬해도 순서가 어긋나지 않는다. */
export function sortSlots(
  slots: readonly SlotView[],
  sort: ResultSort,
): SlotView[] {
  return slots.toSorted(comparatorFor(sort));
}

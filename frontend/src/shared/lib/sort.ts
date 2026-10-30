export type SortDirection = "asc" | "desc";

export type SortState = { key: string; direction: SortDirection };

/** 머리글을 눌렀을 때의 다음 정렬. 다른 칸은 오름차순부터, 같은 칸은 오름↔내림을 바꾼다. */
export function nextSort(
  current: SortState | undefined,
  key: string,
): SortState {
  if (current?.key !== key) {
    return { key, direction: "asc" };
  }
  return { key, direction: current.direction === "asc" ? "desc" : "asc" };
}

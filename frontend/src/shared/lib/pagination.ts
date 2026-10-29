/** 항목이 하나도 없어도 1페이지로 본다. */
export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

const MAX_PAGE_BUTTONS = 5;

/** 현재 페이지를 가운데에 두고, 앞뒤 끝에서는 밀어서 최대 5개의 페이지 번호를 고른다. */
export function visiblePages(current: number, totalPages: number): number[] {
  const count = Math.min(MAX_PAGE_BUTTONS, totalPages);
  const start = Math.min(
    Math.max(1, current - Math.floor(MAX_PAGE_BUTTONS / 2)),
    totalPages - count + 1,
  );
  return Array.from({ length: count }, (_, index) => start + index);
}

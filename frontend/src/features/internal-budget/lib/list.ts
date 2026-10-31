import type { Column } from "../../../shared/components/ui/DataTable";
import type { SortState } from "../../../shared/lib/sort";
import type { BUDGET_LIST_SORTS, BudgetListView } from "./search";

/** 머리글 정렬 조작. 정렬은 서버가 한다. */
export type SortControls = {
  sort?: SortState;
  onSortChange: (key: string) => void;
};

/** 페이지 이동 조작. 전체보기에서만 쓴다. */
export type PagingControls = {
  page: number;
  onPageChange: (page: number) => void;
};

/**
 * 목록 표의 칸 정의. 칸 key는 그 표의 정렬 허용 목록(BUDGET_LIST_SORTS)에 있는 값만 쓸 수 있다.
 * 한쪽만 바꾸면 타입 검사에서 잡혀, 눌러도 정렬이 조용히 버려지는 일을 막는다.
 */
export type ListColumn<View extends BudgetListView> = Omit<
  Column<never>,
  "key" | "render" | "sortable"
> & { key: (typeof BUDGET_LIST_SORTS)[View][number] };

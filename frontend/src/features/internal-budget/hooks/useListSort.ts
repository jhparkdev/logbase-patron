import { getRouteApi } from "@tanstack/react-router";
import { nextSort } from "../../../shared/lib/sort";
import type { SortControls } from "../lib/list";
import { type BudgetListView, listSortOf, listSortParams } from "../lib/search";

const route = getRouteApi("/_app/internal-budget");

/** 그 표의 정렬을 주소에서 읽고, 머리글을 누르면 주소에 남긴다. 정렬이 바뀌면 1페이지로 돌아간다. */
export function useListSort(view: BudgetListView): SortControls {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const sort = listSortOf(search, view);
  return {
    sort,
    onSortChange: (key) =>
      navigate({
        search: (prev) => ({
          ...prev,
          ...listSortParams(view, nextSort(sort, key)),
          page: undefined,
        }),
      }),
  };
}

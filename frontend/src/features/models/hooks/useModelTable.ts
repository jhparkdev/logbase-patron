import { getRouteApi } from "@tanstack/react-router";
import { nextSort } from "../../../shared/lib/sort";
import { modelSortOf, modelSortParams } from "../lib/search";

const route = getRouteApi("/_app/models");

/** 표 정렬을 주소에서 읽고, 머리글 클릭 시 주소에 저장 */
export function useModelSort() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const sort = modelSortOf(search);
  return {
    sort,
    onSortChange: (key: string) =>
      navigate({
        search: (prev) => ({
          ...prev,
          ...modelSortParams(nextSort(sort, key)),
        }),
      }),
  };
}

/** 페이지 이동. 주소에 저장 */
export function useModelPageChange() {
  const navigate = route.useNavigate();
  return (page: number) => navigate({ search: (prev) => ({ ...prev, page }) });
}

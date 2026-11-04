import { getRouteApi } from "@tanstack/react-router";
import { nextSort } from "../../../shared/lib/sort";
import {
  customerSortOf,
  customerSortParams,
  requestSortOf,
  requestSortParams,
} from "../lib/search";

const route = getRouteApi("/_app/customer-usage");

/** 고객 표의 정렬을 주소에서 읽고, 머리글을 누르면 주소에 남긴다. */
export function useCustomerSort() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const sort = customerSortOf(search);
  return {
    sort,
    onSortChange: (key: string) =>
      navigate({
        search: (prev) => ({
          ...prev,
          ...customerSortParams(nextSort(sort, key)),
        }),
        resetScroll: false,
      }),
  };
}

/** 호출 표의 정렬을 주소에서 읽고, 머리글을 누르면 주소에 남긴다. */
export function useRequestSort() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const sort = requestSortOf(search);
  return {
    sort,
    onSortChange: (key: string) =>
      navigate({
        search: (prev) => ({
          ...prev,
          ...requestSortParams(nextSort(sort, key)),
        }),
        resetScroll: false,
      }),
  };
}

/** 전체보기의 페이지 이동. 페이지는 주소에 남긴다. */
export function usePageChange() {
  const navigate = route.useNavigate();
  return (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }), resetScroll: false });
}

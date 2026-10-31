import { getRouteApi } from "@tanstack/react-router";
import { TextLink } from "../../../shared/components/ui/TextLink";
import { nextSort } from "../../../shared/lib/sort";
import type { ListControls } from "../lib/list";
import type { BudgetListView } from "../lib/search";
import { ProjectBudgetTable } from "./ProjectBudgetTable";
import { RequestHistoryTable } from "./RequestHistoryTable";
import { SubscriptionTable } from "./SubscriptionTable";

const route = getRouteApi("/_app/internal-budget");

type BudgetFullListProps = {
  view: BudgetListView;
  /** 예산을 비교하는 달 "YYYY-MM" */
  month: string;
};

/** 전체보기 화면. 고른 목록 하나를 정렬·페이지와 함께 보여 준다. 정렬과 페이지는 주소에 남긴다. */
export function BudgetFullList({ view, month }: BudgetFullListProps) {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const sort =
    search.sort && search.order
      ? { key: search.sort, direction: search.order }
      : undefined;
  const list: ListControls = {
    sort,
    onSortChange: (key) => {
      const next = nextSort(sort, key);
      navigate({
        search: (prev) => ({
          ...prev,
          sort: next.key,
          order: next.direction,
          page: undefined,
        }),
      });
    },
    page: search.page ?? 1,
    onPageChange: (page) => navigate({ search: (prev) => ({ ...prev, page }) }),
  };

  return (
    <>
      <TextLink
        from="/internal-budget"
        to="/internal-budget"
        // 조회 기간만 남기고 목록·정렬·페이지 값은 지운다.
        search={(prev) => ({ from: prev.from, to: prev.to })}
        className="self-start text-body-sm"
      >
        <span aria-hidden="true">‹ </span>요약으로 돌아가기
      </TextLink>
      {view === "projects" && <ProjectBudgetTable month={month} list={list} />}
      {view === "subscriptions" && <SubscriptionTable list={list} />}
      {view === "requests" && <RequestHistoryTable list={list} />}
    </>
  );
}

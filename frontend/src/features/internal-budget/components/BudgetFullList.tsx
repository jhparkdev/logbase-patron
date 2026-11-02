import { getRouteApi } from "@tanstack/react-router";
import { TextLink } from "../../../shared/components/ui/TextLink";
import type { BudgetListView, BudgetSearch } from "../lib/search";
import { ProjectBudgetTable } from "./ProjectBudgetTable";
import { RequestHistoryTable } from "./RequestHistoryTable";
import { SubscriptionTable } from "./SubscriptionTable";

const route = getRouteApi("/_app/internal-budget");

type BudgetFullListProps = {
  view: BudgetListView;
  /** 화면에 보여 주는 조회 조건. 다시 불러오는 동안은 이전 조건이다. */
  search: BudgetSearch;
  refreshing: boolean;
};

/** 전체보기 화면. 고른 목록 하나를 페이지 이동과 함께 보여 준다. 정렬은 표가 맡는다. */
export function BudgetFullList({
  view,
  search,
  refreshing,
}: BudgetFullListProps) {
  const navigate = route.useNavigate();
  const onPageChange = (page: number) =>
    navigate({ search: (prev) => ({ ...prev, page }) });

  return (
    <>
      <TextLink
        from="/internal-budget"
        to="/internal-budget"
        // 목록·페이지 값만 지운다. 표의 정렬은 요약 화면에서도 이어진다.
        search={(prev) => ({ ...prev, view: undefined, page: undefined })}
        className="self-start text-body-sm"
      >
        <span aria-hidden="true">‹ </span>요약으로 돌아가기
      </TextLink>
      {view === "projects" && (
        <ProjectBudgetTable
          search={search}
          refreshing={refreshing}
          onPageChange={onPageChange}
        />
      )}
      {view === "subscriptions" && (
        <SubscriptionTable
          search={search}
          refreshing={refreshing}
          onPageChange={onPageChange}
        />
      )}
      {view === "requests" && (
        <RequestHistoryTable
          search={search}
          refreshing={refreshing}
          onPageChange={onPageChange}
        />
      )}
    </>
  );
}

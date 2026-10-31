import { getRouteApi } from "@tanstack/react-router";
import { TextLink } from "../../../shared/components/ui/TextLink";
import type { PagingControls } from "../lib/list";
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

/** 전체보기 화면. 고른 목록 하나를 페이지 이동과 함께 보여 준다. 정렬은 표가 맡는다. */
export function BudgetFullList({ view, month }: BudgetFullListProps) {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const paging: PagingControls = {
    page: search.page ?? 1,
    onPageChange: (page) => navigate({ search: (prev) => ({ ...prev, page }) }),
  };

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
        <ProjectBudgetTable month={month} paging={paging} />
      )}
      {view === "subscriptions" && <SubscriptionTable paging={paging} />}
      {view === "requests" && <RequestHistoryTable paging={paging} />}
    </>
  );
}

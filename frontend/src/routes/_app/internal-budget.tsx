import { createFileRoute } from "@tanstack/react-router";
import { BudgetFilters } from "../../features/internal-budget/components/BudgetFilters";
import { BudgetFullList } from "../../features/internal-budget/components/BudgetFullList";
import { CostTrendCard } from "../../features/internal-budget/components/CostTrendCard";
import { MemberUsageTable } from "../../features/internal-budget/components/MemberUsageTable";
import { ProjectBudgetTable } from "../../features/internal-budget/components/ProjectBudgetTable";
import { ProjectPanel } from "../../features/internal-budget/components/ProjectPanel";
import { RequestHistoryTable } from "../../features/internal-budget/components/RequestHistoryTable";
import { SubscriptionPanel } from "../../features/internal-budget/components/SubscriptionPanel";
import { SubscriptionTable } from "../../features/internal-budget/components/SubscriptionTable";
import { SummarySkeleton } from "../../features/internal-budget/components/SummarySkeleton";
import { parseBudgetSearch } from "../../features/internal-budget/lib/search";
import { PageHeader } from "../../shared/components/ui/PageHeader";

export const Route = createFileRoute("/_app/internal-budget")({
  // 주소를 읽을 때마다 현재 시각으로 기본 기간(이번 달)을 정한다.
  validateSearch: (search) => parseBudgetSearch(search, new Date()),
  component: InternalBudgetPage,
});

function InternalBudgetPage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  // 예산은 월 단위라 조회 기간 종료일이 속한 달과 비교한다.
  const month = search.to.slice(0, 7);
  // 패널을 닫으면 패널 값만 지우고 조회 조건·목록은 그대로 둔다.
  const closePanel = () =>
    navigate({
      search: (prev) => ({
        ...prev,
        project: undefined,
        subscription: undefined,
      }),
    });

  return (
    <>
      <PageHeader
        title="내부 AI 예산 관리"
        description="사내 프로젝트의 API 비용과 구독료를 함께 관리할 수 있어요."
      />
      <BudgetFilters
        // 뒤로 가기처럼 주소가 바깥에서 바뀌면 폼을 새 값으로 다시 그린다.
        key={`${search.from}~${search.to}`}
        period={{ from: search.from, to: search.to }}
        onSubmit={(period) =>
          navigate({
            search: (prev) => ({ ...prev, ...period, page: undefined }),
          })
        }
      />
      {search.view === undefined ? (
        <>
          {/* 요약 값은 비용 요약 API가 생기면 채운다. 그 전까지는 불러오는 중 모양이다. */}
          <SummarySkeleton />
          <CostTrendCard />
          <ProjectBudgetTable month={month} />
          <SubscriptionTable />
          <MemberUsageTable />
          <RequestHistoryTable />
        </>
      ) : (
        <BudgetFullList view={search.view} month={month} />
      )}
      {search.project !== undefined && (
        <ProjectPanel month={month} onClose={closePanel} />
      )}
      {search.subscription === "new" && (
        <SubscriptionPanel month={month} onClose={closePanel} />
      )}
    </>
  );
}

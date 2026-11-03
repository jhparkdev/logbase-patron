import { createFileRoute } from "@tanstack/react-router";
import { useDeferredValue } from "react";
import {
  internalSummaryQuery,
  projectRowsOptions,
  requestRowsOptions,
  subscriptionRowsOptions,
} from "../../features/internal-budget/api/budget";
import { BudgetFilters } from "../../features/internal-budget/components/BudgetFilters";
import { BudgetFullList } from "../../features/internal-budget/components/BudgetFullList";
import { ProjectBudgetTable } from "../../features/internal-budget/components/ProjectBudgetTable";
import { ProjectPanel } from "../../features/internal-budget/components/ProjectPanel";
import { RequestHistoryTable } from "../../features/internal-budget/components/RequestHistoryTable";
import { SubscriptionPanel } from "../../features/internal-budget/components/SubscriptionPanel";
import { SubscriptionTable } from "../../features/internal-budget/components/SubscriptionTable";
import { SummaryCards } from "../../features/internal-budget/components/SummaryCards";
import { SummarySkeleton } from "../../features/internal-budget/components/SummarySkeleton";
import {
  budgetSearchSchema,
  filterFormValues,
  filterSearchParams,
} from "../../features/internal-budget/lib/search";
import { BudgetStatusNotice } from "../../shared/components/budget/BudgetStatusNotice";
import { DataBlock } from "../../shared/components/ui/DataBlock";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { RefreshingBar } from "../../shared/components/ui/RefreshingBar";
import { budgetMonthOf } from "../../shared/lib/budget";

export const Route = createFileRoute("/_app/internal-budget")({
  validateSearch: budgetSearchSchema,
  loaderDeps: ({ search }) => search,
  // 화면 틀을 먼저 그리도록 기다리지 않는다. 실패는 블록마다 따로 보여 주므로 여기서 멈추지 않는다.
  loader: ({ context: { queryClient }, deps }) => {
    if (deps.view === undefined || deps.view === "projects") {
      void queryClient.prefetchQuery(projectRowsOptions(deps));
    }
    if (deps.view === undefined || deps.view === "subscriptions") {
      void queryClient.prefetchQuery(subscriptionRowsOptions(deps));
    }
    if (deps.view === undefined || deps.view === "requests") {
      void queryClient.prefetchQuery(requestRowsOptions(deps));
    }
    if (deps.view === undefined) {
      void queryClient.prefetchQuery(internalSummaryQuery(deps));
    }
  },
  component: InternalBudgetPage,
});

function InternalBudgetPage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  // 조건을 바꿔 다시 불러오는 동안 이전 결과를 보여 주고, 새 결과가 오면 바꾼다.
  const shown = useDeferredValue(search);
  const refreshing = shown !== search;
  const month = budgetMonthOf(search);
  // 패널을 닫으면 패널 값만 지우고 조회 조건·목록은 그대로 둔다.
  const closePanel = () =>
    navigate({
      search: (prev) => ({
        ...prev,
        detail: undefined,
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
        key={`${search.from}~${search.to}~${search.project}~${search.model}`}
        values={filterFormValues(search)}
        onSubmit={(values) =>
          navigate({
            search: (prev) => ({ ...prev, ...filterSearchParams(values) }),
          })
        }
      />
      {search.budgetStatus && (
        <BudgetStatusNotice
          status={search.budgetStatus}
          onClear={() =>
            void navigate({
              search: (prev) => ({
                ...prev,
                budgetStatus: undefined,
                page: undefined,
              }),
            })
          }
        />
      )}
      {search.view === undefined ? (
        <>
          <div className="relative">
            {refreshing && <RefreshingBar />}
            <DataBlock
              fallback={<SummarySkeleton />}
              errorTitle="요약을 불러오지 못했어요"
              resetKey={JSON.stringify(internalSummaryQuery(shown).queryKey)}
            >
              <SummaryCards filter={shown} />
            </DataBlock>
          </div>
          <ProjectBudgetTable search={shown} refreshing={refreshing} />
          <SubscriptionTable search={shown} refreshing={refreshing} />
          <RequestHistoryTable search={shown} refreshing={refreshing} />
        </>
      ) : (
        <BudgetFullList
          view={search.view}
          search={shown}
          refreshing={refreshing}
        />
      )}
      {search.detail !== undefined && (
        <ProjectPanel
          projectId={search.detail}
          month={month}
          onClose={closePanel}
        />
      )}
      {search.subscription !== undefined && (
        <SubscriptionPanel
          subscription={search.subscription}
          search={shown}
          month={month}
          onClose={closePanel}
        />
      )}
    </>
  );
}

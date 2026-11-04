import { createFileRoute } from "@tanstack/react-router";
import { useDeferredValue } from "react";
import {
  customerRowsOptions,
  requestRowsOptions,
  usageSummaryQuery,
  usageTrendQuery,
} from "../../features/customer-usage/api/usage";
import { CustomerPanel } from "../../features/customer-usage/components/CustomerPanel";
import { CustomerUsageTable } from "../../features/customer-usage/components/CustomerUsageTable";
import { RequestTable } from "../../features/customer-usage/components/RequestTable";
import { SummaryCards } from "../../features/customer-usage/components/SummaryCards";
import { SummarySkeleton } from "../../features/customer-usage/components/SummarySkeleton";
import { UsageFilters } from "../../features/customer-usage/components/UsageFilters";
import { UsageFullList } from "../../features/customer-usage/components/UsageFullList";
import { UsageTrendCard } from "../../features/customer-usage/components/UsageTrendCard";
import {
  customerUsageSearchSchema,
  filterFormValues,
  filterSearchParams,
} from "../../features/customer-usage/lib/search";
import { BudgetStatusNotice } from "../../shared/components/budget/BudgetStatusNotice";
import { DataBlock } from "../../shared/components/ui/DataBlock";
import { PageHeader } from "../../shared/components/ui/PageHeader";
import { RefreshingBar } from "../../shared/components/ui/RefreshingBar";
import { budgetMonthOf } from "../../shared/lib/budget";

export const Route = createFileRoute("/_app/customer-usage")({
  validateSearch: customerUsageSearchSchema,
  loaderDeps: ({ search }) => search,
  // 화면 틀을 먼저 그리도록 기다리지 않는다. 실패는 블록마다 따로 보여 주므로 여기서 멈추지 않는다.
  loader: ({ context: { queryClient }, deps }) => {
    if (deps.view === undefined || deps.view === "customers") {
      void queryClient.prefetchQuery(customerRowsOptions(deps));
    }
    if (deps.view === undefined || deps.view === "requests") {
      void queryClient.prefetchQuery(requestRowsOptions(deps));
    }
    if (deps.view === undefined) {
      void queryClient.prefetchQuery(usageSummaryQuery(deps));
      void queryClient.prefetchQuery(usageTrendQuery(deps));
    }
  },
  component: CustomerUsagePage,
});

function CustomerUsagePage() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  // 조건을 바꿔 다시 불러오는 동안 이전 결과를 보여 주고, 새 결과가 오면 바꾼다.
  const shown = useDeferredValue(search);
  const refreshing = shown !== search;
  const { from, to, customer, service, model, view, detail } = search;
  const budgetMonth = budgetMonthOf({ from, to });

  return (
    <>
      <PageHeader
        title="고객 AI 사용 현황"
        description="고객별 AI 이용 및 비용 현황을 한눈에 확인할 수 있어요."
      />
      <UsageFilters
        // 뒤로 가기처럼 주소가 바깥에서 바뀌면 폼을 새 값으로 다시 그린다.
        key={`${from}~${to}~${customer}~${service}~${model}`}
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
      {view === undefined ? (
        <>
          <div className="relative">
            {refreshing && <RefreshingBar />}
            <DataBlock
              fallback={<SummarySkeleton />}
              errorTitle="요약을 불러오지 못했어요"
              resetKey={JSON.stringify(usageSummaryQuery(shown).queryKey)}
            >
              <SummaryCards search={shown} />
            </DataBlock>
          </div>
          <UsageTrendCard search={shown} refreshing={refreshing} />
          <CustomerUsageTable
            search={shown}
            refreshing={refreshing}
            budgetMonth={budgetMonthOf(shown)}
          />
          <RequestTable search={shown} refreshing={refreshing} />
        </>
      ) : (
        <UsageFullList
          view={view}
          search={shown}
          refreshing={refreshing}
          budgetMonth={budgetMonthOf(shown)}
        />
      )}
      {detail !== undefined && (
        <CustomerPanel
          customerId={detail}
          budgetMonth={budgetMonth}
          onClose={() =>
            navigate({
              search: (prev) => ({ ...prev, detail: undefined }),
              resetScroll: false,
            })
          }
        />
      )}
    </>
  );
}

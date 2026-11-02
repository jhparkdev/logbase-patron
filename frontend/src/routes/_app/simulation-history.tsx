import { createFileRoute } from "@tanstack/react-router";
import {
  historyListOptions,
  historyModelsQuery,
  historyScenariosQuery,
} from "../../features/simulation-history/api/history";
import { HistoryPage } from "../../features/simulation-history/components/HistoryPage";
import { useHistoryData } from "../../features/simulation-history/hooks/useHistoryData";
import { historySearchSchema } from "../../features/simulation-history/lib/search";
import { SimulationResults } from "../../features/simulator/components/SimulationResults";
import { toRunView } from "../../features/simulator/lib/run-view";

export const Route = createFileRoute("/_app/simulation-history")({
  validateSearch: historySearchSchema,
  loaderDeps: ({ search }) => search,
  // 화면 틀을 먼저 그리도록 대기하지 않음. 실패는 목록 블록이 처리하므로 여기서 중단하지 않음
  loader: ({ context: { queryClient }, deps }) => {
    void queryClient.prefetchQuery(historyListOptions(deps));
    void queryClient.prefetchQuery(historyModelsQuery);
    void queryClient.prefetchQuery(historyScenariosQuery);
  },
  component: HistoryRoute,
});

function HistoryRoute() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const data = useHistoryData(search);
  return (
    <HistoryPage
      search={search}
      onSearch={(value) => {
        void navigate({ search: value, resetScroll: false });
      }}
      view={data.view}
      detail={data.detail}
      models={data.models}
      scenarios={data.scenarios}
      onRetry={data.retryList}
      onRetryDetail={data.retryDetail}
      onRerun={(key) => {
        void navigate({
          to: "/simulator",
          search: { sourceRun: key, sort: "model", direction: "asc" },
        });
      }}
      renderResults={() =>
        data.run && (
          <SimulationResults
            view={{ kind: "ready", run: toRunView(data.run) }}
          />
        )
      }
    />
  );
}

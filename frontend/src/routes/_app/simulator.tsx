import { createFileRoute } from "@tanstack/react-router";
import { activeModelsQuery } from "../../features/simulator/api/simulator";
import { SimulatorPage } from "../../features/simulator/components/SimulatorPage";
import { SimulatorRestore } from "../../features/simulator/components/SimulatorRestore";
import { useModelFavorites } from "../../features/simulator/hooks/useModelFavorites";
import { useSimulatorData } from "../../features/simulator/hooks/useSimulatorData";
import { simulatorSearchSchema } from "../../features/simulator/lib/search";

export const Route = createFileRoute("/_app/simulator")({
  validateSearch: simulatorSearchSchema,
  // 화면 틀을 먼저 그리도록 대기하지 않음. 실패는 모델 선택 영역이 처리한다
  loader: ({ context: { queryClient } }) => {
    void queryClient.prefetchQuery(activeModelsQuery);
  },
  component: SimulatorRoute,
});

function SimulatorRoute() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const sort = { key: search.sort, direction: search.direction };
  const data = useSimulatorData({
    runId: search.run,
    sourceRun: search.sourceRun,
    sort,
    onStarted: (simulationId) => {
      void navigate({
        search: (previous) => ({ ...previous, run: simulationId }),
        resetScroll: false,
      });
    },
  });
  const favorites = useModelFavorites();
  const page = {
    catalogState: data.catalogState,
    onRetryCatalog: data.onRetryCatalog,
    onRun: data.onRun,
    imageLimits: data.imageLimits,
    sort,
    onSort: (next: typeof sort) => {
      void navigate({
        search: (previous) => ({
          ...previous,
          sort: next.key,
          direction: next.direction,
        }),
        resetScroll: false,
      });
    },
    ...data.results,
  };
  if (search.sourceRun)
    return (
      <SimulatorRestore
        sourceKey={search.sourceRun}
        view={data.restore}
        onRetry={data.retryDraft}
        favorites={favorites}
        page={page}
      />
    );
  return (
    <SimulatorPage
      choices={data.choices}
      scenarios={data.scenarios}
      favorites={favorites}
      {...page}
    />
  );
}

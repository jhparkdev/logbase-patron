import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  historyListOptions,
  historyModelsQuery,
  historyScenariosQuery,
  rerunDraftOptions,
  runDetailOptions,
} from "../api/history";
import type { HistoryListView } from "../lib/presentation";
import type { HistorySearch } from "../lib/search";
import {
  historyDetailState,
  scenarioNames,
  toHistoryRow,
  toModelOptions,
  toScenarioOptions,
} from "../lib/view";

/** P-05가 쓰는 서버 상태를 화면 값으로 묶는다. 상세는 열었을 때만 조회한다. */
export function useHistoryData(search: HistorySearch) {
  // 조건을 바꾸는 동안 기존 결과를 유지한다
  const list = useQuery({
    ...historyListOptions(search),
    placeholderData: keepPreviousData,
  });
  const models = useQuery(historyModelsQuery);
  const scenarios = useQuery(historyScenariosQuery);
  const names = scenarioNames(scenarios.data?.items ?? []);
  const opened = search.detail ? search.selected : undefined;
  const run = useQuery({
    ...runDetailOptions(opened ?? ""),
    enabled: !!opened,
  });
  const draft = useQuery({
    ...rerunDraftOptions(opened ?? ""),
    enabled: !!opened,
  });
  const view: HistoryListView = list.isError
    ? { kind: "error" }
    : list.data
      ? {
          kind: "ready",
          items: list.data.items.map((item) => toHistoryRow(item, names)),
          total: list.data.total,
          refreshing: list.isPlaceholderData,
        }
      : { kind: "loading" };
  return {
    view,
    detail: historyDetailState(run, draft),
    models: toModelOptions(models.data?.items ?? []),
    scenarios: toScenarioOptions(scenarios.data?.items ?? []),
    run: run.data,
    retryList: () => void list.refetch(),
    retryDetail: () => {
      void run.refetch();
      void draft.refetch();
    },
  };
}

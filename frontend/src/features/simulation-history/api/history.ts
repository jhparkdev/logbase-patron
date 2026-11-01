import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import { type HistorySearch, historyListQuery } from "../lib/search";
import { isRunOngoing } from "../lib/view";

const ROOT_KEY = "simulation-history";
/** 실행 상태와 비용 대조로 바뀔 수 있어 짧게 캐시 */
const HISTORY_STALE_TIME_MS = 30_000;
/** 모델 선택지는 등록할 때만 늘어난다. */
const MODEL_OPTIONS_STALE_TIME_MS = 5 * 60_000;
/** 진행 중인 실행을 다시 읽는 간격. 백엔드 진행 조회 계약의 5초와 같다. */
const RUN_POLL_INTERVAL_MS = 5_000;
/** 모델 목록 API의 한 페이지 최대 크기 */
const MODEL_OPTIONS_PAGE_SIZE = 100;

/** 이력 목록. 조회 조건별로 캐시 */
export function historyListOptions(search: HistorySearch) {
  const query = historyListQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "list", query],
    queryFn: async () =>
      unwrap(await api.GET("/api/simulations", { params: { query } })),
    staleTime: HISTORY_STALE_TIME_MS,
    // 자동 재시도 없음. 사용자가 [다시 시도]로 재조회
    retry: false,
  });
}

/** 진행·결과 조회. 끝나지 않은 실행만 폴링 */
export function runDetailOptions(simulationId: string) {
  return queryOptions({
    queryKey: [ROOT_KEY, "run", simulationId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/simulations/{simulation_id}", {
          params: { path: { simulation_id: simulationId } },
        }),
      ),
    staleTime: HISTORY_STALE_TIME_MS,
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.summary.status;
      return status && isRunOngoing(status) ? RUN_POLL_INTERVAL_MS : false;
    },
  });
}

/** 당시 입력과 모델의 현재 상태. 읽기만 하며 실행을 시작하지 않는다. */
export function rerunDraftOptions(simulationId: string) {
  return queryOptions({
    queryKey: [ROOT_KEY, "rerun-draft", simulationId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/simulations/{simulation_id}/rerun-draft", {
          params: { path: { simulation_id: simulationId } },
        }),
      ),
    staleTime: HISTORY_STALE_TIME_MS,
    retry: false,
  });
}

/** 모델 필터 선택지. 비활성 모델의 과거 실행도 찾도록 상태로 거르지 않는다. */
export const historyModelsQuery = queryOptions({
  queryKey: [ROOT_KEY, "models"],
  queryFn: async () =>
    unwrap(
      await api.GET("/api/models", {
        params: {
          query: {
            sort: "display_name",
            order: "asc",
            page_size: MODEL_OPTIONS_PAGE_SIZE,
          },
        },
      }),
    ),
  staleTime: MODEL_OPTIONS_STALE_TIME_MS,
  retry: false,
});

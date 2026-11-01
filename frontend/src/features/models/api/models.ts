import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import { type ModelsSearch, modelListQuery } from "../lib/search";

/** 목록 한 줄. 백엔드 ModelRead 계약 그대로 */
export type ModelRow = components["schemas"]["ModelRead"];

const ROOT_KEY = "models";
/** 테스트·상태 변경으로 목록이 바뀌므로 짧게 캐시 */
const LIST_STALE_TIME_MS = 30_000;

/** 목록 조회. 조회 조건별로 캐시 */
export function modelListOptions(search: ModelsSearch) {
  const query = modelListQuery(search);
  return queryOptions({
    queryKey: [ROOT_KEY, "list", query],
    // 실패 시 ApiError를 던져 DataBlock이 오류 표시
    queryFn: async () =>
      unwrap(await api.GET("/api/models", { params: { query } })),
    staleTime: LIST_STALE_TIME_MS,
    // 자동 재시도 없음. 사용자가 [다시 시도]로 재조회
    retry: false,
  });
}

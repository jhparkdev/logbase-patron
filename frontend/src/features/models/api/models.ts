import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import { type ModelsSearch, modelListQuery } from "../lib/search";

/** 목록 한 줄. 백엔드 ModelRead 계약 그대로 */
export type ModelRow = components["schemas"]["ModelRead"];
/** 상세. 목록 한 줄에 활성화·비활성화·마지막 성공 테스트 시각이 더해짐 */
export type ModelDetail = components["schemas"]["ModelDetailRead"];

const ROOT_KEY = "models";
/** 목록 조회 캐시 전체의 키. 모델이 바뀌면 이 키로 다시 불러옴 */
export const MODEL_LIST_KEY = [ROOT_KEY, "list"];
/** 테스트·상태 변경으로 목록·상세가 바뀌므로 짧게 캐시 */
const MODEL_STALE_TIME_MS = 30_000;
/** 제공사는 모델을 등록할 때만 바뀐다. */
const PROVIDERS_STALE_TIME_MS = 5 * 60_000;

/** 목록 조회. 조회 조건별로 캐시 */
export function modelListOptions(search: ModelsSearch) {
  const query = modelListQuery(search);
  return queryOptions({
    queryKey: [...MODEL_LIST_KEY, query],
    // 실패 시 ApiError를 던져 DataBlock이 오류 표시
    queryFn: async () =>
      unwrap(await api.GET("/api/models", { params: { query } })),
    staleTime: MODEL_STALE_TIME_MS,
    // 자동 재시도 없음. 사용자가 [다시 시도]로 재조회
    retry: false,
  });
}

/** 제공사 선택지. 모델 목록의 provider 조건에 그대로 쓰는 값 */
export const modelProvidersQuery = queryOptions({
  queryKey: [ROOT_KEY, "providers"],
  queryFn: async () => unwrap(await api.GET("/api/models/providers")),
  staleTime: PROVIDERS_STALE_TIME_MS,
  retry: false,
});

/** 상세 조회. 목록과 같은 시간만 캐시 */
export function modelDetailQuery(modelId: number) {
  return queryOptions({
    queryKey: [ROOT_KEY, "detail", modelId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/models/{model_id}", {
          params: { path: { model_id: modelId } },
        }),
      ),
    staleTime: MODEL_STALE_TIME_MS,
    retry: false,
  });
}

/** 수정할 항목. 보낸 항목만 바뀌고 보내지 않은 항목은 그대로 */
export type ModelInfoChange = components["schemas"]["ModelUpdate"];

/** 표시 이름·용도 수정. 응답은 수정된 상세 */
export async function updateModelInfo(modelId: number, body: ModelInfoChange) {
  return unwrap(
    await api.PATCH("/api/models/{model_id}", {
      params: { path: { model_id: modelId } },
      body,
    }),
  );
}

/** 연결 테스트 결과. 실패한 테스트도 오류가 아니라 이 모양으로 돌아옴 */
export type ConnectionTestResult =
  components["schemas"]["ConnectionTestResult"];

/** 연결 테스트 실행. 실제 AI 호출이라 비용이 듦 */
export async function runConnectionTest(modelId: number, prompt: string) {
  return unwrap(
    await api.POST("/api/models/{model_id}/test", {
      params: { path: { model_id: modelId } },
      body: { prompt },
    }),
  );
}

/** 상태 변경. 가능 여부는 서버가 판단하고, 거절되면 이유가 담긴 오류로 돌아옴 */
export async function changeModelStatus(
  modelId: number,
  status: components["schemas"]["ModelStatus"],
) {
  return unwrap(
    await api.PATCH("/api/models/{model_id}/status", {
      params: { path: { model_id: modelId } },
      body: { status },
    }),
  );
}

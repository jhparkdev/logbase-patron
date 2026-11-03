import { queryOptions } from "@tanstack/react-query";
import { api, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";
import { PAGE_SIZE } from "../../../shared/lib/pagination";
import { RANKING_INPUT_TOKENS, RANKING_OUTPUT_TOKENS } from "../lib/ranking";
import { type ModelsSearch, modelListQuery } from "../lib/search";

/** 목록 한 줄. 백엔드 ModelRead 계약 그대로 */
export type ModelRow = components["schemas"]["ModelRead"];
/** OpenRouter 모델 검색 결과 한 줄. 등록 여부(registered)가 함께 옴 */
export type OpenRouterModel = components["schemas"]["OpenRouterModelRead"];
/** 신규 등록 요청. 상태와 OpenRouter 정보는 서버가 정함 */
export type ModelRegistration = components["schemas"]["ModelCreate"];
/** 상세. 목록 한 줄에 활성화·비활성화·마지막 성공 테스트 시각이 더해짐 */
export type ModelDetail = components["schemas"]["ModelDetailRead"];

const ROOT_KEY = "models";
/** 목록 조회 캐시 전체의 키. 모델이 바뀌면 이 키로 다시 불러옴 */
export const MODEL_LIST_KEY = [ROOT_KEY, "list"];
/** 제공사 선택지 캐시의 키 */
export const MODEL_PROVIDERS_KEY = [ROOT_KEY, "providers"];
/** OpenRouter 검색 결과 캐시 전체의 키 */
export const OPENROUTER_MODELS_KEY = [ROOT_KEY, "openrouter"];
/** 테스트·상태 변경으로 목록·상세가 바뀌므로 짧게 캐시 */
const MODEL_STALE_TIME_MS = 30_000;
/** 제공사는 모델을 등록할 때만 바뀐다. */
const PROVIDERS_STALE_TIME_MS = 5 * 60_000;
/** 등록하면 바로 다시 불러오므로 잠깐만 캐시 */
const OPENROUTER_STALE_TIME_MS = 60_000;
/** 새 모델은 자주 늘지 않아 화면을 오갈 때마다 다시 묻지 않음 */
const NEW_MODELS_STALE_TIME_MS = 5 * 60_000;
/** 이 일수 안에 OpenRouter에 올라온 모델을 새 모델로 봄 */
export const NEW_MODELS_DAYS = 5;
/** 개수(total)만 알면 되므로 모델은 서버가 허용하는 최소 1개만 받음 */
const NEW_MODELS_LIMIT = 1;

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
  queryKey: MODEL_PROVIDERS_KEY,
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

/** OpenRouter 모델 검색. 이미 등록된 모델은 registered로 표시되어 옴 */
export function openRouterModelsQuery(search: {
  q?: string;
  page: number;
  /** 있으면 이 일수 안에 올라온 미등록 모델만, 최근 순으로 받음 */
  newDays?: number;
}) {
  const query = {
    q: search.q,
    new_days: search.newDays,
    page: search.page,
    page_size: PAGE_SIZE,
  };
  return queryOptions({
    queryKey: [...OPENROUTER_MODELS_KEY, query],
    queryFn: async () =>
      unwrap(await api.GET("/api/models/openrouter", { params: { query } })),
    staleTime: OPENROUTER_STALE_TIME_MS,
    retry: false,
  });
}

/**
 * 최근에 올라왔고 아직 등록하지 않은 OpenRouter 모델. 모델 관리 화면의 알림에 씀.
 * 키가 OPENROUTER_MODELS_KEY 아래라서 모델을 등록하면 함께 다시 불러옴
 */
export const newOpenRouterModelsQuery = queryOptions({
  queryKey: [...OPENROUTER_MODELS_KEY, "new"],
  queryFn: async () =>
    unwrap(
      await api.GET("/api/models/openrouter/new", {
        params: {
          query: { days: NEW_MODELS_DAYS, limit: NEW_MODELS_LIMIT },
        },
      }),
    ),
  staleTime: NEW_MODELS_STALE_TIME_MS,
  retry: false,
});

/** 업체는 자주 바뀌지 않으므로 서버의 10분 보관에 맞춰 화면에서도 잠깐 캐시 */
const RANKING_STALE_TIME_MS = 5 * 60_000;

/** 모델의 서버 업체를 예상 총비용이 싼 순서로 받음. cacheHitRatio는 0~1 비율 문자열 */
export function providerRankingQuery(modelId: number, cacheHitRatio: string) {
  return queryOptions({
    queryKey: [ROOT_KEY, "ranking", modelId, cacheHitRatio],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/models/{model_id}/execution-providers/ranking", {
          params: {
            path: { model_id: modelId },
            query: {
              input_tokens: RANKING_INPUT_TOKENS,
              output_tokens: RANKING_OUTPUT_TOKENS,
              cache_hit_ratio: cacheHitRatio,
            },
          },
        }),
      ),
    staleTime: RANKING_STALE_TIME_MS,
    retry: false,
  });
}

/** 신규 등록. 응답은 TESTING 상태로 만들어진 모델의 상세 */
export async function registerModel(body: ModelRegistration) {
  return unwrap(await api.POST("/api/models", { body }));
}

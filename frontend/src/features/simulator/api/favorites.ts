import { queryOptions } from "@tanstack/react-query";
import { api, toApiError, unwrap } from "../../../shared/api/client";
import type { components } from "../../../shared/api/schema";

type FavoriteKey = components["schemas"]["ModelFavoriteKey"];

/** 즐겨찾기는 이 화면에서만 바뀌고 바꿀 때 캐시를 직접 고친다. */
const FAVORITES_STALE_TIME_MS = 5 * 60_000;

export const FAVORITES_KEY = ["simulator", "model-favorites"];
export const FAVORITE_MUTATION_KEY = [...FAVORITES_KEY, "set"];

export const modelFavoritesQuery = queryOptions({
  queryKey: FAVORITES_KEY,
  queryFn: async () => unwrap(await api.GET("/api/model-favorites")),
  staleTime: FAVORITES_STALE_TIME_MS,
  retry: false,
});

/** 이미 있으면 서버가 200으로 같은 항목을 돌려준다. */
export async function addModelFavorite(body: FavoriteKey) {
  return unwrap(await api.POST("/api/model-favorites", { body }));
}

/** 성공은 본문 없는 204라 unwrap 대신 상태 코드로 판단한다. 없는 항목도 204다. */
export async function removeModelFavorite(query: FavoriteKey) {
  const { response, error } = await api.DELETE("/api/model-favorites", {
    params: { query },
  });
  if (!response.ok) throw toApiError(response.status, error);
}

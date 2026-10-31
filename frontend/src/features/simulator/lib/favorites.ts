import { searchModels } from "./model-selection";
import type { ModelChoice } from "./presentation";

// 화면 전용 계약. 조회·저장·오류와 계정별 캐시는 API adapter가 소유한다.
// keys는 모델·Provider 조합인 ModelChoice.key다. 비교 칸이나 실행 설정의 ID가 아니다.
// onSet은 mutation을 요청하고, 그 담당자가 keys/savingKeys/failedKeys를 갱신한다.
export type ModelFavoritesView =
  | { kind: "unavailable" | "loading" }
  | { kind: "error"; onRetry?: () => void }
  | {
      kind: "ready";
      keys: readonly string[];
      savingKeys?: readonly string[];
      failedKeys?: readonly string[];
      onSet: (key: string, favorite: boolean) => void;
    };

export const unavailableFavorites: ModelFavoritesView = { kind: "unavailable" };

export function searchFavoriteModels(
  choices: ModelChoice[],
  query: string,
  favoritesOnly: boolean,
  favorites: ModelFavoritesView,
) {
  const matches = searchModels(choices, query);
  if (!favoritesOnly) return matches;
  if (favorites.kind !== "ready") return [];
  return matches.filter((choice) => favorites.keys.includes(choice.key));
}

export function emptyCatalogMessage(
  query: string,
  favoritesOnly: boolean,
  favorites: ModelFavoritesView,
) {
  if (favoritesOnly && favorites.kind === "ready" && !favorites.keys.length)
    return {
      title: "아직 즐겨찾기한 모델이 없습니다",
      description:
        "전체 모델에서 별 버튼을 눌러 자주 쓰는 모델을 모아 볼 수 있습니다.",
    };
  if (query)
    return {
      title: "검색 결과가 없습니다",
      description: "다른 모델명이나 Provider로 검색하시기 바랍니다.",
    };
  return favoritesOnly
    ? {
        title: "현재 목록에 즐겨찾기한 모델이 없습니다",
        description: "전체 모델에서 모델 목록을 확인하시기 바랍니다.",
      }
    : {
        title: "선택할 수 있는 모델이 없습니다",
        description: "AI 모델 관리에서 모델 목록을 확인하시기 바랍니다.",
      };
}

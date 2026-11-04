import type { components } from "../../../shared/api/schema";
import { choiceKey } from "./catalog";
import type { ModelFavoritesView } from "./favorites";

type Favorite = components["schemas"]["ModelFavoriteRead"];

function keyOf(favorite: Favorite) {
  return choiceKey(favorite.model_id, favorite.execution_provider);
}

export function favoriteKeys(items: readonly Favorite[]): string[] {
  return items.map(keyOf);
}

export function findFavorite(
  items: readonly Favorite[],
  key: string,
): Favorite | undefined {
  return items.find((item) => keyOf(item) === key);
}

/** 서버 목록처럼 최근 등록을 앞에 둔다. 이미 있으면 받은 값으로 바꾼다. */
export function withFavorite(
  items: readonly Favorite[],
  favorite: Favorite,
): Favorite[] {
  const key = keyOf(favorite);
  return [favorite, ...items.filter((item) => keyOf(item) !== key)];
}

export function withoutFavorite(
  items: readonly Favorite[],
  key: string,
): Favorite[] {
  return items.filter((item) => keyOf(item) !== key);
}

export function toFavoritesView(state: {
  status: "pending" | "error" | "success";
  items?: readonly Favorite[];
  savingKeys?: readonly string[];
  failedKeys?: readonly string[];
  onSet: (key: string, favorite: boolean) => void;
  onRetry: () => void;
}): ModelFavoritesView {
  if (state.status === "error")
    return { kind: "error", onRetry: state.onRetry };
  if (state.status === "pending" || !state.items) return { kind: "loading" };
  return {
    kind: "ready",
    keys: favoriteKeys(state.items),
    savingKeys: state.savingKeys,
    failedKeys: state.failedKeys,
    onSet: state.onSet,
  };
}

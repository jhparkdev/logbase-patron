import {
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";
import {
  addModelFavorite,
  FAVORITE_MUTATION_KEY,
  modelFavoritesQuery,
  removeModelFavorite,
} from "../api/favorites";
import { parseChoiceKey } from "../lib/catalog";
import {
  findFavorite,
  toFavoritesView,
  withFavorite,
  withoutFavorite,
} from "../lib/favorite-list";
import type { ModelFavoritesView } from "../lib/favorites";

type Change = {
  key: string;
  target: { model_id: number; execution_provider: string };
  favorite: boolean;
};

/** 즐겨찾기 조회와 등록·해제. 누르면 바로 반영하고, 실패한 항목만 되돌린다. */
export function useModelFavorites(): ModelFavoritesView {
  const queryClient = useQueryClient();
  const queryKey = modelFavoritesQuery.queryKey;
  const favorites = useQuery(modelFavoritesQuery);
  const [failedKeys, setFailedKeys] = useState<readonly string[]>([]);
  const savingKeys = useMutationState({
    filters: { mutationKey: FAVORITE_MUTATION_KEY, status: "pending" },
    select: (mutation) => (mutation.state.variables as Change).key,
  });
  const markFailed = (key: string, failed: boolean) =>
    setFailedKeys((keys) => [
      ...keys.filter((item) => item !== key),
      ...(failed ? [key] : []),
    ]);

  const mutation = useMutation({
    mutationKey: FAVORITE_MUTATION_KEY,
    mutationFn: async ({ target, favorite }: Change) => {
      if (favorite) return addModelFavorite(target);
      await removeModelFavorite(target);
      return undefined;
    },
    onMutate: async ({ key, target, favorite }) => {
      markFailed(key, false);
      // 진행 중인 조회가 늦게 도착해 방금 누른 값을 덮지 않게 멈춘다
      await queryClient.cancelQueries({ queryKey });
      const previous = findFavorite(
        queryClient.getQueryData(queryKey)?.items ?? [],
        key,
      );
      queryClient.setQueryData(queryKey, (data) =>
        data
          ? {
              items: favorite
                ? withFavorite(data.items, {
                    ...target,
                    created_at: new Date().toISOString(),
                  })
                : withoutFavorite(data.items, key),
            }
          : data,
      );
      return { previous };
    },
    onSuccess: (saved) => {
      if (saved)
        queryClient.setQueryData(queryKey, (data) =>
          data ? { items: withFavorite(data.items, saved) } : data,
        );
    },
    onError: (_error, { key, favorite }, context) => {
      queryClient.setQueryData(queryKey, (data) => {
        if (!data) return data;
        const reverted = withoutFavorite(data.items, key);
        return {
          items:
            !favorite && context?.previous
              ? withFavorite(reverted, context.previous)
              : reverted,
        };
      });
      markFailed(key, true);
    },
    onSettled: () => {
      // 다른 항목을 저장하는 중이면 다시 읽지 않는다. 그 항목의 낙관적 표시를 덮기 때문이다
      if (queryClient.isMutating({ mutationKey: FAVORITE_MUTATION_KEY }) === 1)
        return queryClient.invalidateQueries({ queryKey });
    },
  });

  return toFavoritesView({
    status: favorites.status,
    items: favorites.data?.items,
    savingKeys,
    failedKeys,
    onRetry: () => void favorites.refetch(),
    onSet: (key, favorite) => {
      const target = parseChoiceKey(key);
      if (!target) return markFailed(key, true);
      mutation.mutate({ key, target, favorite });
    },
  });
}
